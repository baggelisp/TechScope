"""The port through which a use case hands a finished report to the outside world."""

from pathlib import Path
from typing import Protocol

from techscope.domain.models import ScanReport


class ScanReportWriter(Protocol):
    """Persists a scan report. Implemented in ``infrastructure/writers``."""

    def write(self, report: ScanReport, destination: Path) -> None: ...
