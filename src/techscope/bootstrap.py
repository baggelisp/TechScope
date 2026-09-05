"""Composition root: the only module that knows which concrete adapters are plugged in.

Every driver — the CLI today, the HTTP API from backlog item 10 — enters here. Nothing else in
the package constructs an adapter, so swapping one is a change to this file alone.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from techscope.application.ports.fingerprint_repository import FingerprintRepository
from techscope.application.ports.scan_report_writer import ScanReportWriter
from techscope.application.ports.signal_collector import SignalCollector
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import DomainScanResult, FingerprintIndex, ScanReport
from techscope.infrastructure.collectors.http_collector import HttpSignalCollector
from techscope.infrastructure.http.homepage_fetcher import (
    RETRY_BACKOFF_SECONDS,
    TOTAL_TIMEOUT_SECONDS,
    HomepageFetcher,
    build_client,
)
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)
from techscope.infrastructure.writers.json_report_writer import JsonReportWriter

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 10
# Re-exported so the CLI can offer the real per-domain bound as its default.
DEFAULT_TIMEOUT_SECONDS = TOTAL_TIMEOUT_SECONDS
# Re-exported so the CLI can offer it as a default without importing infrastructure.
DEFAULT_FINGERPRINTS_PATH = DEFAULT_TECHNOLOGIES_PATH


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """Everything a driver must decide before a scan starts."""

    domains: tuple[str, ...]
    output_path: Path
    fingerprints_path: Path
    concurrency: int
    timeout_seconds: float


def run_scan(options: ScanOptions) -> ScanReport:
    """Run one scan end to end and persist its report."""
    return asyncio.run(_run_scan(options))


async def _run_scan(options: ScanOptions) -> ScanReport:
    index = _load_fingerprint_index(options.fingerprints_path)

    async with build_client() as client:
        fetcher = HomepageFetcher(
            client=client,
            retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
            total_timeout_seconds=options.timeout_seconds,
        )
        collectors: tuple[SignalCollector, ...] = (HttpSignalCollector(fetcher=fetcher),)
        scan_domain = ScanDomainUseCase(collectors=collectors, fingerprint_index=index)
        results = await _scan_every_domain(scan_domain, options.domains)

    report = ScanReport(results=results)
    writer: ScanReportWriter = JsonReportWriter()
    writer.write(report, options.output_path)

    return report


async def _scan_every_domain(
    scan_domain: ScanDomainUseCase, domains: tuple[str, ...]
) -> tuple[DomainScanResult, ...]:
    """One domain at a time. Backlog item 8 replaces this with the bounded concurrent run."""
    results: list[DomainScanResult] = []

    for domain in domains:
        results.append(await scan_domain.execute(domain))

    return tuple(results)


def _load_fingerprint_index(fingerprints_path: Path) -> FingerprintIndex:
    repository: FingerprintRepository = JsonFingerprintRepository(fingerprints_path)
    fingerprints = repository.load()
    index = build_fingerprint_index(fingerprints)
    logger.info(
        "loaded %d technologies across %d channels",
        len(fingerprints),
        len(index.patterns_by_channel),
    )

    return index
