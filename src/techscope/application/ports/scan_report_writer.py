"""The port through which a use case hands a finished report to the outside world."""

from pathlib import Path
from typing import Protocol

from techscope.domain.models import ScanReport


class ScanReportWriter(Protocol):
    """Persists a scan report. Implemented in ``infrastructure/writers``."""

    def write_summary(self, report: ScanReport, destination: Path) -> None:
        """The assignment's shape: ``{ "<domain>": [technologies] }``."""
        ...

    def write_details(self, report: ScanReport, destination: Path) -> None:
        """Everything behind the summary: evidence, problems and timings."""
        ...
