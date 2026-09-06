"""Composition root: the only module that knows which concrete adapters are plugged in.

Every driver — the CLI today, the HTTP API from backlog item 10 — enters here. Nothing else in
the package constructs an adapter, so swapping one is a change to this file alone.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from techscope.application.ports.fingerprint_repository import FingerprintRepository
from techscope.application.ports.scan_report_writer import ScanReportWriter
from techscope.application.ports.signal_collector import SignalCollector
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.application.use_cases.scan_domains import ScanDomainsUseCase
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import FingerprintIndex, ScanReport
from techscope.infrastructure.collectors.dns_collector import DnsSignalCollector
from techscope.infrastructure.collectors.http_collector import HttpSignalCollector
from techscope.infrastructure.dns.resolver import DnsPythonResolver, build_async_resolver
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
# Under the assignment's 60 s, with room to write the output after the last domain lands.
DEFAULT_DEADLINE_SECONDS = 55.0
# Re-exported so the CLI can offer it as a default without importing infrastructure.
DEFAULT_FINGERPRINTS_PATH = DEFAULT_TECHNOLOGIES_PATH


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """Everything a driver must decide before a scan starts."""

    domains: tuple[str, ...]
    output_path: Path
    details_path: Path | None
    fingerprints_path: Path
    nameservers: tuple[str, ...]
    concurrency: int
    timeout_seconds: float
    deadline_seconds: float


def run_scan(options: ScanOptions) -> ScanReport:
    """Run one scan end to end and persist its report."""
    return asyncio.run(_run_scan(options))


async def _run_scan(options: ScanOptions) -> ScanReport:
    index = _load_fingerprint_index(options.fingerprints_path)

    async with build_client() as client:
        scan_domains = _build_scan_domains(client, index, options)
        report = await scan_domains.execute(options.domains)

    _write_report(report, options)

    return report


def _build_scan_domains(
    client: httpx.AsyncClient, index: FingerprintIndex, options: ScanOptions
) -> ScanDomainsUseCase:
    fetcher = HomepageFetcher(
        client=client,
        retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
        total_timeout_seconds=options.timeout_seconds,
    )
    resolver = DnsPythonResolver(build_async_resolver(options.nameservers))
    collectors: tuple[SignalCollector, ...] = (
        HttpSignalCollector(fetcher=fetcher),
        DnsSignalCollector(resolver=resolver),
    )
    scan_domain = ScanDomainUseCase(collectors=collectors, fingerprint_index=index)

    return ScanDomainsUseCase(
        scan_domain=scan_domain,
        concurrency=options.concurrency,
        deadline_seconds=options.deadline_seconds,
    )


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


def _write_report(report: ScanReport, options: ScanOptions) -> None:
    writer: ScanReportWriter = JsonReportWriter()
    writer.write_summary(report, options.output_path)

    if options.details_path is None:
        return

    writer.write_details(report, options.details_path)
