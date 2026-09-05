"""Records shared across layers. Frozen, slotted, and free of any I/O concern.

Two halves meet in the matcher: ``Signal`` is what a collector observed, ``Pattern`` and
``Fingerprint`` are what the database says to look for, and ``Detection`` with its ``Evidence``
is the answer.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from techscope.domain.enums import ChannelEnum


@dataclass(frozen=True, slots=True)
class Pattern:
    """One compiled Wappalyzer pattern, ready to test against a signal.

    ``key_regex`` constrains the signal's name on a keyed channel and is ``None`` elsewhere.
    Both source strings are kept so a detection can quote the pattern that produced it.
    """

    channel: ChannelEnum
    value_regex: re.Pattern[str]
    key_regex: re.Pattern[str] | None
    confidence: int
    version_template: str | None
    value_source: str
    key_source: str | None

    def decide_source_text(self) -> str:
        """How this pattern reads in a detection's evidence."""
        if self.key_source is None:
            return self.value_source

        if len(self.value_source) == 0:
            return self.key_source

        return f"{self.key_source}: {self.value_source}"


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Everything the database says about one technology."""

    name: str
    patterns: tuple[Pattern, ...]
    implies: tuple[str, ...]
    categories: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class IndexedPattern:
    """A pattern together with the technology it would prove."""

    technology: str
    pattern: Pattern


@dataclass(frozen=True, slots=True)
class FingerprintIndex:
    """Patterns grouped by channel once at load time, so matching never scans the whole set."""

    patterns_by_channel: Mapping[ChannelEnum, tuple[IndexedPattern, ...]]
    fingerprint_by_name: Mapping[str, Fingerprint]

    def list_patterns(self, channel: ChannelEnum) -> tuple[IndexedPattern, ...]:
        patterns = self.patterns_by_channel.get(channel)

        if patterns is None:
            return ()

        return patterns

    def decide_fingerprint_or_none(self, name: str) -> Fingerprint | None:
        return self.fingerprint_by_name.get(name)


@dataclass(frozen=True, slots=True)
class Signal:
    """One observation, whatever collected it.

    ``key`` names the observation on a keyed channel — a header name, a cookie name, a meta tag
    name, a JavaScript global — and is ``None`` on the rest. The matcher never learns which
    collector produced a signal, which is what lets a new source be a new adapter alone.
    """

    channel: ChannelEnum
    value: str
    key: str | None = None


@dataclass(frozen=True, slots=True)
class Evidence:
    """Why a technology was reported: the signal that matched and the pattern that matched it."""

    channel: ChannelEnum
    key: str | None
    pattern_source: str
    matched_text: str


@dataclass(frozen=True, slots=True)
class Detection:
    """One technology found on one domain, with everything needed to justify it."""

    name: str
    confidence: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class DomainScanResult:
    """What one scanned domain produced: the technologies detected on it."""

    domain: str
    technologies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScanReport:
    """One whole run, holding a result per input domain in input order."""

    results: tuple[DomainScanResult, ...]
