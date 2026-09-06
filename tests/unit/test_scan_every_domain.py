"""The bounded fan-out: every domain comes back, in order, whatever happens to one of them.

Concurrency moved here from backlog item 8 when DNS put the run over the assignment's budget, so
the properties item 8 would have tested are pinned here instead.
"""

import asyncio

from techscope.bootstrap import scan_every_domain
from techscope.domain.enums import FailureReasonEnum
from techscope.domain.models import Detection, DomainScanResult

DOMAINS = ("first.example", "second.example", "third.example", "fourth.example")


class FakeScanDomain:
    """Stands in for the use case: records concurrency, and can be slow or explosive."""

    def __init__(self, pause_seconds: float = 0.0, failing_domain: str | None = None) -> None:
        self.scanned: list[str] = []
        self.peak_in_flight = 0
        self._in_flight = 0
        self._pause_seconds = pause_seconds
        self._failing_domain = failing_domain

    async def execute(self, domain: str) -> DomainScanResult:
        self._in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self._in_flight)

        try:
            await asyncio.sleep(self._pause_seconds)

            if domain == self._failing_domain:
                raise RuntimeError("something unexpected")

            self.scanned.append(domain)

            return DomainScanResult(
                domain=domain,
                detections=(Detection(name="Some Tech", confidence=100, evidence=()),),
                failures=(),
            )
        finally:
            self._in_flight -= 1


async def test_scan_every_domain_returns_a_result_per_domain_in_input_order() -> None:
    results = await scan_every_domain(FakeScanDomain(), DOMAINS, concurrency=2)

    assert tuple(result.domain for result in results) == DOMAINS


async def test_scan_every_domain_scans_every_domain() -> None:
    scan_domain = FakeScanDomain()

    await scan_every_domain(scan_domain, DOMAINS, concurrency=2)

    assert sorted(scan_domain.scanned) == sorted(DOMAINS)


async def test_scan_every_domain_respects_the_concurrency_limit() -> None:
    scan_domain = FakeScanDomain(pause_seconds=0.02)

    await scan_every_domain(scan_domain, DOMAINS, concurrency=2)

    assert scan_domain.peak_in_flight == 2


async def test_scan_every_domain_runs_domains_in_parallel() -> None:
    pause = 0.05
    scan_domain = FakeScanDomain(pause_seconds=pause)

    started_at = asyncio.get_running_loop().time()
    await scan_every_domain(scan_domain, DOMAINS, concurrency=len(DOMAINS))
    elapsed = asyncio.get_running_loop().time() - started_at

    assert elapsed < pause * len(DOMAINS)


async def test_scan_every_domain_scans_one_at_a_time_when_told_to() -> None:
    scan_domain = FakeScanDomain(pause_seconds=0.01)

    await scan_every_domain(scan_domain, DOMAINS, concurrency=1)

    assert scan_domain.peak_in_flight == 1


async def test_scan_every_domain_keeps_a_domain_whose_scan_exploded() -> None:
    """One unexpected failure must cost that domain, never the whole run's output."""
    scan_domain = FakeScanDomain(failing_domain="second.example")

    results = await scan_every_domain(scan_domain, DOMAINS, concurrency=2)

    assert tuple(result.domain for result in results) == DOMAINS


async def test_scan_every_domain_records_why_a_scan_exploded() -> None:
    scan_domain = FakeScanDomain(failing_domain="second.example")

    results = await scan_every_domain(scan_domain, DOMAINS, concurrency=2)
    failed = [result for result in results if result.domain == "second.example"]

    assert failed[0].detections == ()
    assert failed[0].failures[0].reason is FailureReasonEnum.COLLECTOR_ERROR


async def test_scan_every_domain_keeps_the_other_domains_detections() -> None:
    scan_domain = FakeScanDomain(failing_domain="second.example")

    results = await scan_every_domain(scan_domain, DOMAINS, concurrency=2)
    healthy = [result for result in results if result.domain != "second.example"]

    assert [len(result.detections) for result in healthy] == [1, 1, 1]


async def test_scan_every_domain_of_no_domains_returns_nothing() -> None:
    assert await scan_every_domain(FakeScanDomain(), (), concurrency=2) == ()
