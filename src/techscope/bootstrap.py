"""Composition root: the only module that knows which concrete adapters are plugged in.

Every driver — the CLI today, the HTTP API from backlog item 10 — enters here. Nothing else in
the package constructs an adapter, so swapping one is a change to this file alone.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from techscope.application.ports.domain_scanner import DomainScanner
from techscope.application.ports.fingerprint_repository import FingerprintRepository
from techscope.application.ports.scan_report_writer import ScanReportWriter
from techscope.application.ports.signal_collector import SignalCollector
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.domain.enums import FailureReasonEnum
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import (
    CollectionFailure,
    DomainScanResult,
    FingerprintIndex,
    ScanReport,
)
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
        collectors: tuple[SignalCollector, ...] = (
            HttpSignalCollector(fetcher=fetcher),
            DnsSignalCollector(resolver=DnsPythonResolver(build_async_resolver())),
        )
        scan_domain = ScanDomainUseCase(collectors=collectors, fingerprint_index=index)
        results = await scan_every_domain(scan_domain, options.domains, options.concurrency)

    report = ScanReport(results=results)
    writer: ScanReportWriter = JsonReportWriter()
    writer.write(report, options.output_path)

    return report


async def scan_every_domain(
    scan_domain: DomainScanner, domains: tuple[str, ...], concurrency: int
) -> tuple[DomainScanResult, ...]:
    """Scan domains in parallel, bounded, and return one result per domain in input order.

    Sequential scanning was enough until DNS joined: three lookups per domain took the run from
    16 s to 61 s, past the 60 s the assignment allows. Backlog item 8 still owns the whole-run
    deadline and the structured output.

    Exceptions are collected rather than raised. Without that, one domain reaching an unexpected
    state would abort the gather and the run would write no output at all — the blast radius
    would be every domain, not the one that failed.
    """
    limit = asyncio.Semaphore(concurrency)

    async def scan_one(domain: str) -> DomainScanResult:
        async with limit:
            return await scan_domain.execute(domain)

    outcomes = await asyncio.gather(
        *(scan_one(domain) for domain in domains), return_exceptions=True
    )

    return tuple(
        _decide_domain_result(domain, outcome)
        for domain, outcome in zip(domains, outcomes, strict=True)
    )


def _decide_domain_result(
    domain: str, outcome: DomainScanResult | BaseException
) -> DomainScanResult:
    if isinstance(outcome, DomainScanResult):
        return outcome

    if not isinstance(outcome, Exception):
        raise outcome

    logger.error("scanning %s failed unexpectedly: %r", domain, outcome)
    failure = CollectionFailure(
        collector="scan", reason=FailureReasonEnum.COLLECTOR_ERROR, detail=repr(outcome)
    )

    return DomainScanResult(domain=domain, detections=(), failures=(failure,))


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
