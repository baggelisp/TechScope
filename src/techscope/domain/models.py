"""Records shared across layers. Frozen, slotted, and free of any I/O concern.

Later features add ``Signal``, ``Pattern``, ``Fingerprint``, ``Evidence`` and ``Detection`` here;
this feature only needs the shape of a finished scan.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainScanResult:
    """What one scanned domain produced: the technologies detected on it."""

    domain: str
    technologies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScanReport:
    """One whole run, holding a result per input domain in input order."""

    results: tuple[DomainScanResult, ...]
