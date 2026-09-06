"""Scanning a list of domains: bounded, timed, and impossible to come back short.

Two guarantees hold whatever happens inside. Every input domain appears in the result, in input
order. And the scan ends by the deadline, because one that never returns is worse than one that
returns partial answers.

The deadline bounds the scan, not the process: work already handed to a worker thread cannot be
cancelled, so the interpreter waits for it on the way out. Today that is one HTML parse over a
body capped at two megabytes, which is milliseconds.
"""

import asyncio
import logging
from dataclasses import replace
from time import perf_counter

from techscope.application.ports.domain_scanner import DomainScanner
from techscope.domain.enums import FailureReasonEnum
from techscope.domain.models import CollectionFailure, DomainScanResult, ScanReport

logger = logging.getLogger(__name__)

ORCHESTRATOR_NAME = "scan"


class ScanDomainsUseCase:
    """Runs the per-domain scan across a list, under a concurrency limit and a deadline."""

    def __init__(
        self, scan_domain: DomainScanner, concurrency: int, deadline_seconds: float
    ) -> None:
        self._scan_domain = scan_domain
        # One limiter for the life of this use case, not one per call. The CLI runs a single
        # scan per process, so nothing changes there; the HTTP API holds one of these for the
        # life of the server, and a per-call limiter would let N simultaneous requests put
        # N times the limit of domains in flight over one connection pool.
        self._limit = asyncio.Semaphore(concurrency)
        self._deadline_seconds = deadline_seconds

    async def execute(self, domains: tuple[str, ...]) -> ScanReport:
        started_at = perf_counter()
        tasks = self._start_tasks(domains)
        await self._await_within_deadline(tasks)
        results = tuple(
            _decide_result(domain, task) for domain, task in zip(domains, tasks, strict=True)
        )
        report = ScanReport(results=results, duration_seconds=perf_counter() - started_at)
        _log_report(report)

        return report

    def _start_tasks(self, domains: tuple[str, ...]) -> tuple[asyncio.Task[DomainScanResult], ...]:
        async def scan_one(domain: str) -> DomainScanResult:
            async with self._limit:
                started_at = perf_counter()
                result = await self._scan_domain.execute(domain)

                return _with_duration(result, perf_counter() - started_at)

        return tuple(asyncio.create_task(scan_one(domain)) for domain in domains)

    async def _await_within_deadline(
        self, tasks: tuple[asyncio.Task[DomainScanResult], ...]
    ) -> None:
        try:
            async with asyncio.timeout(self._deadline_seconds):
                await asyncio.gather(*tasks, return_exceptions=True)
        except TimeoutError:
            # A cancelled task reports done(), so counting those is the only honest measure.
            cut_short_count = sum(1 for task in tasks if task.cancelled())
            logger.error(
                "the scan hit its %.1fs deadline; %d domains were cut short",
                self._deadline_seconds,
                cut_short_count,
            )


def _with_duration(result: DomainScanResult, duration_seconds: float) -> DomainScanResult:
    return replace(result, duration_seconds=duration_seconds)


def _decide_result(domain: str, task: asyncio.Task[DomainScanResult]) -> DomainScanResult:
    """A domain that was cut short by the deadline still appears, saying so."""
    if task.cancelled():
        return _build_failed_result(domain, FailureReasonEnum.TIMEOUT, "cut short by the deadline")

    error = task.exception()

    if error is None:
        return task.result()

    logger.error("scanning %s failed unexpectedly: %r", domain, error)

    return _build_failed_result(domain, FailureReasonEnum.COLLECTOR_ERROR, repr(error))


def _build_failed_result(domain: str, reason: FailureReasonEnum, detail: str) -> DomainScanResult:
    failure = CollectionFailure(collector=ORCHESTRATOR_NAME, reason=reason, detail=detail)

    return DomainScanResult(
        domain=domain,
        detections=(),
        failures=(failure,),
        observed_url=None,
        duration_seconds=None,
    )


def _log_report(report: ScanReport) -> None:
    troubled = report.list_troubled_results()

    for result in troubled:
        reasons = ", ".join(f"{failure.collector}: {failure.reason}" for failure in result.failures)
        logger.warning("%s reported problems (%s)", result.domain, reasons)

    logger.info(
        "scanned %d domains in %.1fs: %d detections, %d domains with problems",
        len(report.results),
        report.duration_seconds,
        report.count_detections(),
        len(troubled),
    )
