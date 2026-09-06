"""Composition root: the only module that knows which concrete adapters are plugged in.

Every driver enters here — the CLI per invocation, the HTTP API once for the life of the
process. Nothing else in the package constructs an adapter, so swapping one is a change to this
file alone.

The two drivers want the wiring for different lengths of time, which is the whole reason
``build_scan_service`` is a context manager and ``run_scan`` is a thin call over it: a scan
holds an HTTP connection pool, and the driver decides how long that lives.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

from techscope.application.ports.fingerprint_repository import FingerprintRepository
from techscope.application.ports.scan_report_writer import ScanReportWriter
from techscope.application.ports.signal_collector import SignalCollector
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.application.use_cases.scan_domains import ScanDomainsUseCase
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import Fingerprint, FingerprintIndex, ScanReport
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
class ScanSettings:
    """How a scan runs, whichever driver asked for it."""

    fingerprints_path: Path
    nameservers: tuple[str, ...]
    concurrency: int
    timeout_seconds: float
    deadline_seconds: float


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """One command-line run: a scan, plus where its files go."""

    domains: tuple[str, ...]
    output_path: Path
    details_path: Path | None
    settings: ScanSettings


@dataclass(frozen=True, slots=True)
class ScanService:
    """Everything a driver needs to serve scans, wired and ready.

    The HTTP client is not here: it belongs to the context manager that opened it, which is the
    only thing that should ever close it.
    """

    scan_domains: ScanDomainsUseCase
    fingerprints: tuple[Fingerprint, ...]


@asynccontextmanager
async def build_scan_service(settings: ScanSettings) -> AsyncIterator[ScanService]:
    """Wire one scanning service and keep it usable for as long as the caller holds it."""
    fingerprints = _load_fingerprints(settings.fingerprints_path)
    index = build_fingerprint_index(fingerprints)

    async with build_client() as client:
        yield ScanService(
            scan_domains=_build_scan_domains(client, index, settings),
            fingerprints=fingerprints,
        )


def run_scan(options: ScanOptions) -> ScanReport:
    """Run one scan end to end and persist its report."""
    return asyncio.run(_run_scan(options))


async def _run_scan(options: ScanOptions) -> ScanReport:
    async with build_scan_service(options.settings) as service:
        report = await service.scan_domains.execute(options.domains)

    _write_report(report, options)

    return report


def _build_scan_domains(
    client: httpx.AsyncClient, index: FingerprintIndex, settings: ScanSettings
) -> ScanDomainsUseCase:
    fetcher = HomepageFetcher(
        client=client,
        retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
        total_timeout_seconds=settings.timeout_seconds,
    )
    resolver = DnsPythonResolver(build_async_resolver(settings.nameservers))
    collectors: tuple[SignalCollector, ...] = (
        HttpSignalCollector(fetcher=fetcher),
        DnsSignalCollector(resolver=resolver),
    )
    scan_domain = ScanDomainUseCase(collectors=collectors, fingerprint_index=index)

    return ScanDomainsUseCase(
        scan_domain=scan_domain,
        concurrency=settings.concurrency,
        deadline_seconds=settings.deadline_seconds,
    )


def _load_fingerprints(fingerprints_path: Path) -> tuple[Fingerprint, ...]:
    repository: FingerprintRepository = JsonFingerprintRepository(fingerprints_path)
    fingerprints = repository.load()
    logger.info("loaded %d technologies from %s", len(fingerprints), fingerprints_path)

    return fingerprints


def _write_report(report: ScanReport, options: ScanOptions) -> None:
    writer: ScanReportWriter = JsonReportWriter()
    writer.write_summary(report, options.output_path)

    if options.details_path is None:
        return

    writer.write_details(report, options.details_path)
