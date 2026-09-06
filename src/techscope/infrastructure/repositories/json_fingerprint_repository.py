"""Loads a Wappalyzer-shaped JSON database into fingerprints.

The shape is the upstream one: a JSON object mapping a technology name to its definition. Keys
this scanner cannot observe over plain HTTP — ``url``, ``dom``, ``xhr``, ``certIssuer`` and the
rest — are ignored rather than rejected, which is what lets the full upstream database load with
no code change. Anything that is present but unusable, such as a regex that will not compile, is
an error: a silently dropped pattern looks exactly like a technology that is not in use.

The document is read as ``object`` and narrowed by hand. That is deliberate: this is the one
boundary where data arrives untyped, and isinstance narrowing keeps the rest of the package free
of ``Any``.
"""

import json
import logging
from pathlib import Path

from techscope.domain.enums import KEYED_CHANNELS, ChannelEnum
from techscope.domain.errors import FingerprintLoadError
from techscope.domain.models import Fingerprint, Implication, Pattern
from techscope.infrastructure.repositories.wappalyzer_pattern import (
    build_implication,
    build_pattern,
)

logger = logging.getLogger(__name__)

DEFAULT_TECHNOLOGIES_PATH = Path(__file__).parent / "data" / "technologies.json"
FILE_ENCODING = "utf-8"
SCHEMA_KEY_PREFIX = "$"
DNS_KEY = "dns"
IMPLIES_KEY = "implies"
CATEGORIES_KEY = "cats"


# The one place an upstream key becomes a channel. Supporting a new key is an entry here.
# Whether a channel is keyed is decided by KEYED_CHANNELS alone, so the two cannot drift.
WAPPALYZER_KEY_TO_CHANNEL: dict[str, ChannelEnum] = {
    "headers": ChannelEnum.HEADER,
    "cookies": ChannelEnum.COOKIE,
    "meta": ChannelEnum.META,
    "js": ChannelEnum.JS_GLOBAL,
    "scriptSrc": ChannelEnum.SCRIPT_SRC,
    "scripts": ChannelEnum.SCRIPT_INLINE,
    "html": ChannelEnum.HTML,
}

DNS_RECORD_TO_CHANNEL: dict[str, ChannelEnum] = {
    "MX": ChannelEnum.DNS_MX,
    "TXT": ChannelEnum.DNS_TXT,
    "CNAME": ChannelEnum.DNS_CNAME,
}


class JsonFingerprintRepository:
    """Reads the fingerprint database from a JSON file on disk."""

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path

    def load(self) -> tuple[Fingerprint, ...]:
        document = self._read_document()
        fingerprints: list[Fingerprint] = []

        for name, definition in document.items():
            if name.startswith(SCHEMA_KEY_PREFIX):
                continue

            fingerprints.append(_build_fingerprint(name, definition))

        logger.debug("loaded %d fingerprints from %s", len(fingerprints), self._data_path)

        return tuple(fingerprints)

    def _read_document(self) -> dict[str, object]:
        try:
            text = self._data_path.read_text(encoding=FILE_ENCODING)
        except OSError as error:
            raise FingerprintLoadError(None, f"cannot read {self._data_path}: {error}") from error

        try:
            parsed: object = json.loads(text)
        except json.JSONDecodeError as error:
            raise FingerprintLoadError(
                None, f"{self._data_path} is not valid JSON: {error}"
            ) from error

        document = _decide_mapping_or_none(parsed)

        if document is None:
            raise FingerprintLoadError(None, f"{self._data_path} must hold a JSON object")

        return document


def _build_fingerprint(name: str, raw_definition: object) -> Fingerprint:
    definition = _decide_mapping_or_none(raw_definition)

    if definition is None:
        raise FingerprintLoadError(name, "the entry must be a JSON object")

    return Fingerprint(
        name=name,
        patterns=_build_patterns(name, definition),
        implies=_build_implications(name, definition.get(IMPLIES_KEY)),
        categories=_build_categories(definition.get(CATEGORIES_KEY)),
    )


def _build_patterns(technology: str, definition: dict[str, object]) -> tuple[Pattern, ...]:
    patterns: list[Pattern] = []

    for wappalyzer_key, raw_value in definition.items():
        patterns.extend(_build_patterns_for_key(technology, wappalyzer_key, raw_value))

    return tuple(patterns)


def _build_patterns_for_key(
    technology: str, wappalyzer_key: str, raw_value: object
) -> list[Pattern]:
    if wappalyzer_key == DNS_KEY:
        return _build_dns_patterns(technology, raw_value)

    channel = WAPPALYZER_KEY_TO_CHANNEL.get(wappalyzer_key)

    if channel is None:
        return []

    if channel in KEYED_CHANNELS:
        return _build_keyed_patterns(technology, channel, raw_value)

    return _build_keyless_patterns(technology, channel, raw_value)


def _build_keyed_patterns(
    technology: str, channel: ChannelEnum, raw_value: object
) -> list[Pattern]:
    entries = _decide_mapping_or_none(raw_value)

    if entries is None:
        raise FingerprintLoadError(technology, f"{channel} patterns must be a JSON object")

    patterns: list[Pattern] = []

    for key, raw_pattern in entries.items():
        patterns.extend(_build_patterns_for_key_entry(technology, channel, key, raw_pattern))

    return patterns


def _build_patterns_for_key_entry(
    technology: str, channel: ChannelEnum, key: str, raw_pattern: object
) -> list[Pattern]:
    texts = _decide_pattern_texts_or_none(raw_pattern)

    if texts is None:
        raise FingerprintLoadError(technology, f"{channel} pattern for {key!r} must be text")

    return [build_pattern(technology, channel, text, key) for text in texts]


def _build_keyless_patterns(
    technology: str, channel: ChannelEnum, raw_value: object
) -> list[Pattern]:
    texts = _decide_pattern_texts_or_none(raw_value)

    if texts is None:
        raise FingerprintLoadError(technology, f"{channel} patterns must be text or a list")

    return [build_pattern(technology, channel, text, None) for text in texts]


def _build_dns_patterns(technology: str, raw_value: object) -> list[Pattern]:
    records = _decide_mapping_or_none(raw_value)

    if records is None:
        raise FingerprintLoadError(technology, "dns patterns must be a JSON object")

    patterns: list[Pattern] = []

    for record_type, raw_patterns in records.items():
        channel = DNS_RECORD_TO_CHANNEL.get(record_type)

        if channel is None:
            continue

        patterns.extend(_build_keyless_patterns(technology, channel, raw_patterns))

    return patterns


def _build_implications(technology: str, raw_value: object) -> tuple[Implication, ...]:
    """An implied technology is reported as a detection, so bad data here is an error."""
    if raw_value is None:
        return ()

    texts = _decide_pattern_texts_or_none(raw_value)

    if texts is None:
        raise FingerprintLoadError(technology, "implies must be text or a list of text")

    return tuple(build_implication(technology, text) for text in texts)


def _build_categories(raw_value: object) -> tuple[int, ...]:
    """Categories are informational only: they never reach a detection, so oddities are dropped."""
    if not isinstance(raw_value, list):
        return ()

    categories: list[int] = [item for item in raw_value if isinstance(item, int)]

    return tuple(categories)


def _decide_mapping_or_none(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    return {str(key): item for key, item in value.items()}


def _decide_pattern_texts_or_none(value: object) -> tuple[str, ...] | None:
    """A pattern value is a string or a list of strings. Anything else is unusable data.

    Coercing a non-string would compile a regex out of it: a JSON ``null`` would become the
    pattern ``None``, which matches that literal text in any signal and fabricates a detection.
    """
    if isinstance(value, str):
        return (value,)

    if not isinstance(value, list):
        return None

    if not all(isinstance(item, str) for item in value):
        return None

    return tuple(item for item in value if isinstance(item, str))
