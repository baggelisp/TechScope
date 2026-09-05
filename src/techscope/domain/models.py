"""Records shared across layers. Frozen, slotted, and free of any I/O concern.

Later features add ``Signal``, ``Evidence`` and ``Detection`` here; this feature covers the
fingerprint side of the matcher.
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
class DomainScanResult:
    """What one scanned domain produced: the technologies detected on it."""

    domain: str
    technologies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScanReport:
    """One whole run, holding a result per input domain in input order."""

    results: tuple[DomainScanResult, ...]
