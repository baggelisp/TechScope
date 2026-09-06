"""Scanning one domain: every collector runs, and one failing never silences the others."""

import asyncio

from techscope.application.ports.signal_collector import CollectionResult
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.domain.enums import BlockReasonEnum, ChannelEnum, FailureReasonEnum
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import CollectionFailure, DomainScanResult, Signal
from tests.support.builders import build_test_fingerprint, build_test_pattern

DOMAIN = "example.com"

STRIPE = build_test_fingerprint(
    "Stripe", (build_test_pattern(ChannelEnum.SCRIPT_SRC, r"js\.stripe\.com/v3"),)
)
CLOUDFLARE = build_test_fingerprint(
    "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
)

STRIPE_SIGNAL = Signal(channel=ChannelEnum.SCRIPT_SRC, value="https://js.stripe.com/v3/")
CLOUDFLARE_SIGNAL = Signal(channel=ChannelEnum.HEADER, value="8abc-DFW", key="cf-ray")


class FakeCollector:
    """A collector that returns what the test tells it to, after an optional pause."""

    def __init__(
        self,
        name: str,
        result: CollectionResult | None = None,
        error: Exception | None = None,
        pause_seconds: float = 0.0,
    ) -> None:
        self.name = name
        self.calls: list[str] = []
        self._result = result
        self._error = error
        self._pause_seconds = pause_seconds

    async def collect(self, domain: str) -> CollectionResult:
        self.calls.append(domain)
        await asyncio.sleep(self._pause_seconds)

        if self._error is not None:
            raise self._error

        if self._result is None:
            return CollectionResult(signals=(), failure=None)

        return self._result


def build_use_case(*collectors: FakeCollector) -> ScanDomainUseCase:
    index = build_fingerprint_index((STRIPE, CLOUDFLARE))

    return ScanDomainUseCase(collectors=tuple(collectors), fingerprint_index=index)


def list_names(result: DomainScanResult) -> list[str]:
    return [detection.name for detection in result.detections]


async def test_scan_domain_carries_the_domain_through() -> None:
    result = await build_use_case(FakeCollector("http")).execute(DOMAIN)

    assert result.domain == DOMAIN


async def test_scan_domain_asks_every_collector() -> None:
    first = FakeCollector("http")
    second = FakeCollector("dns")

    await build_use_case(first, second).execute(DOMAIN)

    assert first.calls == [DOMAIN]
    assert second.calls == [DOMAIN]


async def test_scan_domain_matches_the_signals_it_collected() -> None:
    collector = FakeCollector("http", CollectionResult(signals=(STRIPE_SIGNAL,), failure=None))

    result = await build_use_case(collector).execute(DOMAIN)

    assert list_names(result) == ["Stripe"]


async def test_scan_domain_merges_signals_from_every_collector() -> None:
    http = FakeCollector("http", CollectionResult(signals=(STRIPE_SIGNAL,), failure=None))
    headers = FakeCollector("headers", CollectionResult(signals=(CLOUDFLARE_SIGNAL,), failure=None))

    result = await build_use_case(http, headers).execute(DOMAIN)

    assert list_names(result) == ["Cloudflare", "Stripe"]


async def test_scan_domain_without_signals_detects_nothing() -> None:
    result = await build_use_case(FakeCollector("http")).execute(DOMAIN)

    assert result.detections == ()
    assert result.failures == ()


async def test_scan_domain_records_a_reported_failure() -> None:
    failure = CollectionFailure(
        collector="http", reason=BlockReasonEnum.FORBIDDEN, detail="403 from the host"
    )
    collector = FakeCollector("http", CollectionResult(signals=(), failure=failure))

    result = await build_use_case(collector).execute(DOMAIN)

    assert result.failures == (failure,)


async def test_scan_domain_keeps_the_signals_a_blocked_collector_still_gathered() -> None:
    failure = CollectionFailure(
        collector="http", reason=BlockReasonEnum.CHALLENGE_PAGE, detail="challenge"
    )
    collector = FakeCollector(
        "http", CollectionResult(signals=(CLOUDFLARE_SIGNAL,), failure=failure)
    )

    result = await build_use_case(collector).execute(DOMAIN)

    assert list_names(result) == ["Cloudflare"]
    assert result.failures == (failure,)


async def test_scan_domain_turns_a_raising_collector_into_a_failure() -> None:
    collector = FakeCollector("dns", error=RuntimeError("resolver exploded"))

    result = await build_use_case(collector).execute(DOMAIN)

    assert [failure.reason for failure in result.failures] == [FailureReasonEnum.COLLECTOR_ERROR]
    assert result.failures[0].collector == "dns"


async def test_scan_domain_keeps_the_other_collectors_when_one_raises() -> None:
    healthy = FakeCollector("http", CollectionResult(signals=(STRIPE_SIGNAL,), failure=None))
    broken = FakeCollector("dns", error=RuntimeError("resolver exploded"))

    result = await build_use_case(healthy, broken).execute(DOMAIN)

    assert list_names(result) == ["Stripe"]
    assert len(result.failures) == 1


async def test_scan_domain_runs_its_collectors_concurrently() -> None:
    pause = 0.05
    slow = FakeCollector("http", pause_seconds=pause)
    also_slow = FakeCollector("dns", pause_seconds=pause)

    started_at = asyncio.get_running_loop().time()
    await build_use_case(slow, also_slow).execute(DOMAIN)
    elapsed = asyncio.get_running_loop().time() - started_at

    assert elapsed < pause * 2


async def test_scan_domain_records_the_page_the_http_collector_read() -> None:
    """A domain that redirects to another company must not hide where its signals came from."""
    moved = CollectionResult(
        signals=(STRIPE_SIGNAL,),
        failure=None,
        observed_url="https://www.salesloft.com/platform/chat-agents",
    )
    collector = FakeCollector("http", moved)

    result = await build_use_case(collector).execute(DOMAIN)

    assert result.observed_url == "https://www.salesloft.com/platform/chat-agents"


async def test_scan_domain_reports_no_page_when_nothing_was_fetched() -> None:
    result = await build_use_case(FakeCollector("dns")).execute(DOMAIN)

    assert result.observed_url is None
