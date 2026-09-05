"""Composition root: the only module that knows which concrete adapters are plugged in.

Every driver — the CLI today, the HTTP API from backlog item 10 — enters here. Nothing else in
the package constructs an adapter, so swapping one is a change to this file alone.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from techscope.application.ports.scan_report_writer import ScanReportWriter
from techscope.domain.models import DomainScanResult, ScanReport
from techscope.infrastructure.writers.json_report_writer import JsonReportWriter

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 10
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """Everything a driver must decide before a scan starts."""

    domains: tuple[str, ...]
    output_path: Path
    concurrency: int
    timeout_seconds: float


def run_scan(options: ScanOptions) -> ScanReport:
    """Run one scan end to end and persist its report."""
    report = _build_unscanned_report(options.domains)
    writer: ScanReportWriter = JsonReportWriter()
    writer.write(report, options.output_path)

    return report


def _build_unscanned_report(domains: tuple[str, ...]) -> ScanReport:
    """Placeholder for the collectors and the matcher.

    Backlog item 4 replaces this with ``ScanDomainUseCase``, driven by ``ScanDomainsUseCase``
    from item 8. Until a collector exists there is nothing to detect, so every domain reports
    an empty technology list — which is already the shape the assignment asks for.
    """
    results = tuple(DomainScanResult(domain=domain, technologies=()) for domain in domains)

    return ScanReport(results=results)
