"""Scanning a list of domains: bounded, timed, and never coming back short."""

import asyncio

from techscope.application.use_cases.scan_domains import ScanDomainsUseCase
from techscope.domain.enums import FailureReasonEnum
from techscope.domain.models import Detection, DomainScanResult, ScanReport

DOMAINS = ("first.example", "second.example", "third.example", "fourth.example")
GENEROUS_DEADLINE = 30.0


class FakeScanDomain:
    """Stands in for the per-domain use case: records concurrency, can be slow or explosive."""

    def __init__(
        self,
        pause_seconds: float = 0.0,
        failing_domain: str | None = None,
        slow_domain: str | None = None,
        slow_pause_seconds: float = 0.0,
    ) -> None:
        self.scanned: list[str] = []
        self.peak_in_flight = 0
        self._in_flight = 0
        self._pause_seconds = pause_seconds
        self._failing_domain = failing_domain
        self._slow_domain = slow_domain
        self._slow_pause_seconds = slow_pause_seconds

    async def execute(self, domain: str) -> DomainScanResult:
        self._in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self._in_flight)

        try:
            await asyncio.sleep(self._decide_pause(domain))

            if domain == self._failing_domain:
                raise RuntimeError("something unexpected")

            self.scanned.append(domain)

            return DomainScanResult(
                domain=domain,
                detections=(Detection(name="Some Tech", confidence=100, evidence=()),),
                failures=(),
                duration_seconds=0.0,
            )
        finally:
            self._in_flight -= 1

    def _decide_pause(self, domain: str) -> float:
        if domain == self._slow_domain:
            return self._slow_pause_seconds

        return self._pause_seconds


def build_use_case(
    scan_domain: FakeScanDomain, concurrency: int = 2, deadline_seconds: float = GENEROUS_DEADLINE
) -> ScanDomainsUseCase:
    return ScanDomainsUseCase(
        scan_domain=scan_domain, concurrency=concurrency, deadline_seconds=deadline_seconds
    )


def list_domains(report: ScanReport) -> tuple[str, ...]:
    return tuple(result.domain for result in report.results)


async def test_returns_a_result_per_domain_in_input_order() -> None:
    report = await build_use_case(FakeScanDomain()).execute(DOMAINS)

    assert list_domains(report) == DOMAINS


async def test_scans_every_domain() -> None:
    scan_domain = FakeScanDomain()

    await build_use_case(scan_domain).execute(DOMAINS)

    assert sorted(scan_domain.scanned) == sorted(DOMAINS)


async def test_respects_the_concurrency_limit() -> None:
    scan_domain = FakeScanDomain(pause_seconds=0.02)

    await build_use_case(scan_domain, concurrency=2).execute(DOMAINS)

    assert scan_domain.peak_in_flight == 2


async def test_scans_one_at_a_time_when_told_to() -> None:
    scan_domain = FakeScanDomain(pause_seconds=0.01)

    await build_use_case(scan_domain, concurrency=1).execute(DOMAINS)

    assert scan_domain.peak_in_flight == 1


async def test_runs_domains_in_parallel() -> None:
    pause = 0.05
    scan_domain = FakeScanDomain(pause_seconds=pause)

    report = await build_use_case(scan_domain, concurrency=len(DOMAINS)).execute(DOMAINS)

    assert report.duration_seconds < pause * len(DOMAINS)


async def test_times_the_whole_run() -> None:
    report = await build_use_case(FakeScanDomain(pause_seconds=0.02)).execute(DOMAINS)

    assert report.duration_seconds > 0.0


async def test_times_each_domain() -> None:
    report = await build_use_case(FakeScanDomain(pause_seconds=0.02)).execute(DOMAINS)
    durations = [result.duration_seconds for result in report.results]

    assert all(duration is not None and duration > 0.0 for duration in durations)


async def test_reports_no_duration_for_a_domain_that_was_cut_short() -> None:
    """Zero would make the domains that ran longest look like the fastest."""
    scan_domain = FakeScanDomain(pause_seconds=10.0)

    report = await build_use_case(scan_domain, deadline_seconds=0.05).execute(DOMAINS)

    assert [result.duration_seconds for result in report.results] == [None] * len(DOMAINS)


async def test_counts_the_detections_it_found() -> None:
    report = await build_use_case(FakeScanDomain()).execute(DOMAINS)

    assert report.count_detections() == len(DOMAINS)


async def test_keeps_a_domain_whose_scan_exploded() -> None:
    scan_domain = FakeScanDomain(failing_domain="second.example")

    report = await build_use_case(scan_domain).execute(DOMAINS)

    assert list_domains(report) == DOMAINS


async def test_records_why_a_scan_exploded() -> None:
    scan_domain = FakeScanDomain(failing_domain="second.example")

    report = await build_use_case(scan_domain).execute(DOMAINS)
    failed = [result for result in report.results if result.domain == "second.example"]

    assert failed[0].detections == ()
    assert failed[0].failures[0].reason is FailureReasonEnum.COLLECTOR_ERROR


async def test_keeps_the_other_domains_detections_when_one_explodes() -> None:
    scan_domain = FakeScanDomain(failing_domain="second.example")

    report = await build_use_case(scan_domain).execute(DOMAINS)
    healthy = [result for result in report.results if result.domain != "second.example"]

    assert [len(result.detections) for result in healthy] == [1, 1, 1]


async def test_stops_at_the_deadline() -> None:
    """A scan that never returns is worse than one that returns partial answers."""
    scan_domain = FakeScanDomain(pause_seconds=10.0)

    report = await build_use_case(scan_domain, deadline_seconds=0.05).execute(DOMAINS)

    assert report.duration_seconds < 1.0


async def test_still_reports_every_domain_after_the_deadline() -> None:
    scan_domain = FakeScanDomain(pause_seconds=10.0)

    report = await build_use_case(scan_domain, deadline_seconds=0.05).execute(DOMAINS)

    assert list_domains(report) == DOMAINS


async def test_says_why_a_domain_was_cut_short() -> None:
    scan_domain = FakeScanDomain(pause_seconds=10.0)

    report = await build_use_case(scan_domain, deadline_seconds=0.05).execute(DOMAINS)

    assert [result.failures[0].reason for result in report.results] == [
        FailureReasonEnum.TIMEOUT
    ] * len(DOMAINS)


async def test_keeps_the_domains_that_finished_before_the_deadline() -> None:
    scan_domain = FakeScanDomain(
        pause_seconds=0.0, slow_domain="fourth.example", slow_pause_seconds=10.0
    )

    report = await build_use_case(
        scan_domain, concurrency=len(DOMAINS), deadline_seconds=0.1
    ).execute(DOMAINS)
    finished = [result for result in report.results if len(result.detections) > 0]

    assert [result.domain for result in finished] == list(DOMAINS[:3])


async def test_of_no_domains_reports_nothing() -> None:
    report = await build_use_case(FakeScanDomain()).execute(())

    assert report.results == ()
    assert report.count_detections() == 0
