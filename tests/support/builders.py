"""Builders for domain records, so pure tests never reach for the JSON repository."""

import re

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Fingerprint, Pattern

FULL_CONFIDENCE = 100


def build_test_pattern(
    channel: ChannelEnum,
    value_source: str = "",
    key_source: str | None = None,
    confidence: int = FULL_CONFIDENCE,
) -> Pattern:
    return Pattern(
        channel=channel,
        value_regex=re.compile(value_source, re.IGNORECASE),
        key_regex=_compile_key_or_none(key_source),
        confidence=confidence,
        version_template=None,
        value_source=value_source,
        key_source=key_source,
    )


def build_test_fingerprint(
    name: str, patterns: tuple[Pattern, ...] = (), implies: tuple[str, ...] = ()
) -> Fingerprint:
    return Fingerprint(name=name, patterns=patterns, implies=implies, categories=())


def _compile_key_or_none(key_source: str | None) -> re.Pattern[str] | None:
    if key_source is None:
        return None

    return re.compile(key_source, re.IGNORECASE)
