r"""Parsing the Wappalyzer pattern syntax into a compiled ``Pattern``.

A pattern is a regex optionally followed by modifiers, separated by a literal backslash and
semicolon: ``analytics\.js\;confidence:50\;version:\1``. Understanding the modifiers is what
lets the full upstream database load without a code change; leaving them in the regex would
silently break every pattern that carries one.
"""

import re

from techscope.domain.enums import KEYED_CHANNELS, ChannelEnum
from techscope.domain.errors import FingerprintLoadError
from techscope.domain.models import Pattern
from techscope.infrastructure.repositories.pattern_safety import decide_pattern_danger_or_none

MODIFIER_SEPARATOR = "\\;"
CONFIDENCE_MODIFIER = "confidence:"
VERSION_MODIFIER = "version:"
DEFAULT_CONFIDENCE = 100
MINIMUM_CONFIDENCE = 0
MAXIMUM_CONFIDENCE = 100


def build_pattern(
    technology: str, channel: ChannelEnum, raw_pattern: str, raw_key: str | None
) -> Pattern:
    """Compile one pattern. Raises ``FingerprintLoadError`` naming the technology on bad data."""
    parts = raw_pattern.split(MODIFIER_SEPARATOR)
    regex_text = parts[0]
    modifier_parts = parts[1:]
    _check_pattern_is_not_a_wildcard_or_raise(technology, channel, regex_text)
    check_pattern_is_safe_or_raise(technology, regex_text)

    if raw_key is not None:
        check_pattern_is_safe_or_raise(technology, raw_key)

    return Pattern(
        channel=channel,
        value_regex=_compile_or_raise(technology, regex_text),
        key_regex=_decide_key_regex_or_none(technology, raw_key),
        confidence=_decide_confidence(technology, modifier_parts),
        version_template=_decide_version_template_or_none(modifier_parts),
        value_source=regex_text,
        key_source=raw_key,
    )


def decide_implied_technology(raw_implies: str) -> str:
    """An ``implies`` entry may carry the same modifiers; only the name is a technology."""
    parts = raw_implies.split(MODIFIER_SEPARATOR)

    return parts[0].strip()


def _decide_key_regex_or_none(technology: str, raw_key: str | None) -> re.Pattern[str] | None:
    if raw_key is None:
        return None

    return _compile_or_raise(technology, raw_key)


def _check_pattern_is_not_a_wildcard_or_raise(
    technology: str, channel: ChannelEnum, regex_text: str
) -> None:
    """An empty pattern matches everything, which is only meaningful for a named signal.

    On a keyed channel it reads as "this header exists, whatever its value". On a keyless one it
    would report the technology on every page, so it is rejected rather than silently trusted.
    """
    is_empty = len(regex_text) == 0
    is_keyless = channel not in KEYED_CHANNELS

    if is_empty and is_keyless:
        raise FingerprintLoadError(technology, f"an empty {channel} pattern matches every signal")


def _decide_modifier_or_none(modifier_parts: list[str], prefix: str) -> str | None:
    for part in modifier_parts:
        if part.startswith(prefix):
            return part[len(prefix) :]

    return None


def _decide_confidence(technology: str, modifier_parts: list[str]) -> int:
    text = _decide_modifier_or_none(modifier_parts, CONFIDENCE_MODIFIER)

    if text is None:
        return DEFAULT_CONFIDENCE

    return _decide_confidence_from_text(technology, text)


def _decide_confidence_from_text(technology: str, text: str) -> int:
    try:
        confidence = int(text)
    except ValueError as error:
        raise FingerprintLoadError(
            technology, f"confidence {text!r} is not a whole number"
        ) from error

    _check_confidence_in_range_or_raise(technology, confidence)

    return confidence


def _check_confidence_in_range_or_raise(technology: str, confidence: int) -> None:
    is_below_range = confidence < MINIMUM_CONFIDENCE
    is_above_range = confidence > MAXIMUM_CONFIDENCE

    if is_below_range or is_above_range:
        raise FingerprintLoadError(
            technology,
            f"confidence {confidence} is outside {MINIMUM_CONFIDENCE}-{MAXIMUM_CONFIDENCE}",
        )


def _decide_version_template_or_none(modifier_parts: list[str]) -> str | None:
    return _decide_modifier_or_none(modifier_parts, VERSION_MODIFIER)


def _compile_or_raise(technology: str, regex_text: str) -> re.Pattern[str]:
    try:
        return re.compile(regex_text, re.IGNORECASE)
    except re.error as error:
        raise FingerprintLoadError(technology, f"invalid regex {regex_text!r}: {error}") from error


def check_pattern_is_safe_or_raise(technology: str, regex_text: str) -> None:
    """Refuse a regex that can be driven into exponential backtracking.

    Patterns are data and the pages they run against are not ours. ``re`` has no timeout, so a
    pattern that backtracks is a way to stop the scanner from a page it is scanning.
    """
    danger = decide_pattern_danger_or_none(regex_text)

    if danger is None:
        return

    raise FingerprintLoadError(
        technology,
        f"the pattern {regex_text!r} can backtrack exponentially at {danger!r}",
    )
