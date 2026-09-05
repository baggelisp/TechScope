"""The matching core: signals against fingerprints. Pure — no I/O, no clock, no globals.

Accuracy lives here. A technology is reported only when one of its patterns matched a signal
that was really observed, and every detection carries the evidence that produced it.
"""

import re
from dataclasses import dataclass

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import (
    Detection,
    Evidence,
    Fingerprint,
    FingerprintIndex,
    IndexedPattern,
    Pattern,
    Signal,
)

MINIMUM_REPORTED_CONFIDENCE = 50
MAXIMUM_EVIDENCE_TEXT_LENGTH = 200


@dataclass(frozen=True, slots=True)
class _PatternMatch:
    """One pattern of one technology matching one signal."""

    confidence: int
    evidence: Evidence


def build_fingerprint_index(fingerprints: tuple[Fingerprint, ...]) -> FingerprintIndex:
    """Group every pattern by its channel so a signal only ever meets relevant patterns."""
    patterns_by_channel: dict[ChannelEnum, list[IndexedPattern]] = {}
    fingerprint_by_name: dict[str, Fingerprint] = {}

    for fingerprint in fingerprints:
        fingerprint_by_name[fingerprint.name] = fingerprint

        for pattern in fingerprint.patterns:
            entry = IndexedPattern(technology=fingerprint.name, pattern=pattern)
            patterns_by_channel.setdefault(pattern.channel, []).append(entry)

    return FingerprintIndex(
        patterns_by_channel={
            channel: tuple(entries) for channel, entries in patterns_by_channel.items()
        },
        fingerprint_by_name=fingerprint_by_name,
    )


def match_signals(signals: tuple[Signal, ...], index: FingerprintIndex) -> tuple[Detection, ...]:
    """Resolve the technologies these signals prove, sorted by name and free of duplicates."""
    matches = _collect_pattern_matches(signals, index)
    observed = _decide_confidence_by_technology(matches)
    reported = _decide_reported_confidences(observed)
    with_implications = _add_implied_confidences(reported, index)

    return _build_detections(with_implications, matches)


def _collect_pattern_matches(
    signals: tuple[Signal, ...], index: FingerprintIndex
) -> dict[str, list[_PatternMatch]]:
    matches: dict[str, list[_PatternMatch]] = {}

    for signal in signals:
        for entry in index.list_patterns(signal.channel):
            evidence = _decide_evidence_or_none(signal, entry.pattern)

            if evidence is None:
                continue

            match = _PatternMatch(confidence=entry.pattern.confidence, evidence=evidence)
            matches.setdefault(entry.technology, []).append(match)

    return matches


def _decide_evidence_or_none(signal: Signal, pattern: Pattern) -> Evidence | None:
    if not _is_key_match(signal, pattern):
        return None

    value_match = pattern.value_regex.search(signal.value)

    if value_match is None:
        return None

    return Evidence(
        channel=signal.channel,
        key=signal.key,
        pattern_source=pattern.decide_source_text(),
        matched_text=_decide_matched_text(signal, pattern, value_match),
    )


def _is_key_match(signal: Signal, pattern: Pattern) -> bool:
    """A keyed pattern names the signal exactly, end to end.

    Upstream keys are literal names, so anything short of ``fullmatch`` turns them into
    substring or prefix tests on another technology's name. Measured across the 7,894 keyed
    patterns of the full upstream database, cross-technology key collisions number 883 under
    ``search``, 199 under ``match`` and 3 under ``fullmatch``: ``core-js`` firing on
    ``window.corebine``, the F5 BigIP cookie ``TIN`` firing on ``wp-settings-time-1``. No
    upstream key is written as a prefix, so requiring the whole name costs nothing there; a
    pattern that really means "starts with" says so with its own quantifier.
    """
    if pattern.key_regex is None:
        return True

    if signal.key is None:
        return False

    return pattern.key_regex.fullmatch(signal.key) is not None


def _decide_matched_text(signal: Signal, pattern: Pattern, value_match: re.Match[str]) -> str:
    """What to quote as evidence.

    The matched text, except where the pattern accepts any value — the keyed case, where the
    interesting fact is the value the named signal actually carried.
    """
    accepts_any_value = len(pattern.value_source) == 0
    quoted = _decide_quoted_text(signal, value_match, accepts_any_value)

    return quoted[:MAXIMUM_EVIDENCE_TEXT_LENGTH]


def _decide_quoted_text(signal: Signal, value_match: re.Match[str], accepts_any_value: bool) -> str:
    if accepts_any_value:
        return signal.value

    return value_match.group(0)


def _decide_confidence_by_technology(matches: dict[str, list[_PatternMatch]]) -> dict[str, int]:
    """Wappalyzer semantics: the strongest matching pattern speaks for the technology."""
    confidence_by_technology: dict[str, int] = {}

    for technology, pattern_matches in matches.items():
        confidences = [pattern_match.confidence for pattern_match in pattern_matches]
        confidence_by_technology[technology] = max(confidences)

    return confidence_by_technology


def _decide_reported_confidences(confidence_by_technology: dict[str, int]) -> dict[str, int]:
    reported: dict[str, int] = {}

    for technology, confidence in confidence_by_technology.items():
        if confidence < MINIMUM_REPORTED_CONFIDENCE:
            continue

        reported[technology] = confidence

    return reported


def _add_implied_confidences(
    confidence_by_technology: dict[str, int], index: FingerprintIndex
) -> dict[str, int]:
    """Follow ``implies`` chains, each implication inheriting the confidence that reached it.

    An entry is queued again only when its confidence strictly increases, so a cycle in the data
    settles instead of looping.
    """
    resolved = dict(confidence_by_technology)
    pending = list(confidence_by_technology.items())

    while len(pending) > 0:
        technology, confidence = pending.pop()
        fingerprint = index.decide_fingerprint_or_none(technology)

        if fingerprint is None:
            continue

        for implied in fingerprint.implies:
            if _is_resolved_at_least_as_strongly(resolved, implied, confidence):
                continue

            resolved[implied] = confidence
            pending.append((implied, confidence))

    return resolved


def _is_resolved_at_least_as_strongly(
    resolved: dict[str, int], technology: str, confidence: int
) -> bool:
    known = resolved.get(technology)

    if known is None:
        return False

    return known >= confidence


def _build_detections(
    confidence_by_technology: dict[str, int], matches: dict[str, list[_PatternMatch]]
) -> tuple[Detection, ...]:
    detections: list[Detection] = []

    for technology in sorted(confidence_by_technology, key=str.lower):
        detection = Detection(
            name=technology,
            confidence=confidence_by_technology[technology],
            evidence=_build_evidence(matches, technology),
        )
        detections.append(detection)

    return tuple(detections)


def _build_evidence(
    matches: dict[str, list[_PatternMatch]], technology: str
) -> tuple[Evidence, ...]:
    """An implied technology has no matched pattern of its own, so it carries no evidence."""
    pattern_matches = matches.get(technology, [])

    return tuple(pattern_match.evidence for pattern_match in pattern_matches)
