"""The DNS collector, driven by a fake resolver. No test here touches a nameserver."""

import asyncio

from techscope.domain.enums import ChannelEnum, FailureReasonEnum
from techscope.domain.matcher import build_fingerprint_index, match_signals
from techscope.domain.models import Signal
from techscope.infrastructure.collectors.dns_collector import DnsSignalCollector
from techscope.infrastructure.dns.resolver import DnsAnswer
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)

DOMAIN = "example.com"


class FakeResolver:
    """Answers from a table of (name, record type). Anything unlisted has no records.

    A record type listed in ``failures`` did not complete, the way a timed-out lookup does.
    """

    def __init__(
        self,
        records: dict[tuple[str, str], tuple[str, ...]],
        pause_seconds: float = 0.0,
        failures: dict[tuple[str, str], FailureReasonEnum] | None = None,
    ) -> None:
        self.queries: list[tuple[str, str]] = []
        self._records = records
        self._pause_seconds = pause_seconds
        self._failures = failures or {}

    async def resolve(self, name: str, record_type: str) -> DnsAnswer:
        self.queries.append((name, record_type))
        await asyncio.sleep(self._pause_seconds)
        records = self._records.get((name, record_type), ())
        failure = self._failures.get((name, record_type))

        return DnsAnswer(records=records, failure=failure)


async def collect(resolver: FakeResolver, domain: str = DOMAIN) -> tuple[Signal, ...]:
    result = await DnsSignalCollector(resolver=resolver).collect(domain)

    assert result.failure is None

    return result.signals


def detect(signals: tuple[Signal, ...]) -> list[str]:
    fingerprints = JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()

    return [
        detection.name
        for detection in match_signals(signals, build_fingerprint_index(fingerprints))
    ]


async def test_dns_collector_asks_for_every_record_type() -> None:
    resolver = FakeResolver({})

    await collect(resolver)

    assert sorted(record_type for _, record_type in resolver.queries) == ["CNAME", "MX", "TXT"]


async def test_dns_collector_queries_the_apex_of_a_www_domain() -> None:
    resolver = FakeResolver({})

    await collect(resolver, "www.example.com")

    assert {name for name, _ in resolver.queries} == {"example.com"}


async def test_dns_collector_puts_each_record_type_on_its_own_channel() -> None:
    resolver = FakeResolver(
        {
            (DOMAIN, "MX"): ("10 aspmx.l.google.com.",),
            (DOMAIN, "TXT"): ("v=spf1 include:sendgrid.net ~all",),
            (DOMAIN, "CNAME"): ("example.my.salesforce.com.",),
        }
    )

    signals = await collect(resolver)

    assert {signal.channel for signal in signals} == {
        ChannelEnum.DNS_MX,
        ChannelEnum.DNS_TXT,
        ChannelEnum.DNS_CNAME,
    }


async def test_dns_collector_leaves_a_record_signal_unkeyed() -> None:
    resolver = FakeResolver({(DOMAIN, "MX"): ("10 aspmx.l.google.com.",)})

    signals = await collect(resolver)

    assert signals[0].key is None


async def test_dns_collector_emits_one_signal_per_record() -> None:
    resolver = FakeResolver(
        {(DOMAIN, "MX"): ("10 aspmx.l.google.com.", "20 alt1.aspmx.l.google.com.")}
    )

    assert len(await collect(resolver)) == 2


async def test_dns_collector_of_a_domain_without_records_emits_nothing() -> None:
    assert await collect(FakeResolver({})) == ()


async def test_dns_collector_reports_no_failure_when_a_domain_has_no_records() -> None:
    result = await DnsSignalCollector(resolver=FakeResolver({})).collect(DOMAIN)

    assert result.failure is None


async def test_dns_collector_queries_the_record_types_concurrently() -> None:
    pause = 0.05
    resolver = FakeResolver({}, pause_seconds=pause)

    started_at = asyncio.get_running_loop().time()
    await collect(resolver)
    elapsed = asyncio.get_running_loop().time() - started_at

    assert elapsed < pause * 3


async def test_dns_collector_detects_google_workspace_from_a_mail_exchanger() -> None:
    resolver = FakeResolver({(DOMAIN, "MX"): ("10 aspmx.l.google.com.",)})

    assert detect(await collect(resolver)) == ["Google Workspace"]


async def test_dns_collector_detects_microsoft_365_from_a_mail_exchanger() -> None:
    resolver = FakeResolver({(DOMAIN, "MX"): ("0 example-com.mail.protection.outlook.com.",)})

    assert detect(await collect(resolver)) == ["Microsoft 365"]


async def test_dns_collector_detects_sendgrid_from_a_text_record() -> None:
    resolver = FakeResolver({(DOMAIN, "TXT"): ("v=spf1 include:sendgrid.net ~all",)})

    assert detect(await collect(resolver)) == ["SendGrid"]


async def test_dns_collector_detects_hubspot_from_a_verification_record() -> None:
    resolver = FakeResolver({(DOMAIN, "TXT"): ("hubspot-developer-verification=abc123",)})

    assert detect(await collect(resolver)) == ["HubSpot"]


async def test_dns_collector_detects_salesforce_from_an_alias() -> None:
    resolver = FakeResolver({(DOMAIN, "CNAME"): ("example.my.salesforce.com.",)})

    assert detect(await collect(resolver)) == ["Salesforce"]


async def test_dns_collector_does_not_detect_a_mail_provider_from_the_wrong_record_type() -> None:
    """A mail exchanger pattern must not match a text record that happens to mention it."""
    resolver = FakeResolver({(DOMAIN, "TXT"): ("we migrated away from google.com mail",)})

    assert detect(await collect(resolver)) == []


async def test_dns_collector_does_not_detect_google_workspace_from_googlemail() -> None:
    resolver = FakeResolver({(DOMAIN, "MX"): ("10 aspmx.l.googlemail.co.",)})

    assert detect(await collect(resolver)) == []


async def test_dns_collector_does_not_detect_microsoft_365_from_a_lookalike_host() -> None:
    resolver = FakeResolver({(DOMAIN, "MX"): ("0 example-com.mail.protection.office.com.",)})

    assert detect(await collect(resolver)) == []


async def test_dns_collector_does_not_detect_salesforce_without_the_leading_dot() -> None:
    resolver = FakeResolver({(DOMAIN, "CNAME"): ("example.mysalesforce.com.",)})

    assert detect(await collect(resolver)) == []


async def test_dns_collector_does_not_detect_hubspot_from_a_different_verification() -> None:
    resolver = FakeResolver({(DOMAIN, "TXT"): ("hubspot-verification=abc123",)})

    assert detect(await collect(resolver)) == []


async def test_dns_collector_does_not_detect_sendgrid_from_a_lookalike_domain() -> None:
    resolver = FakeResolver({(DOMAIN, "TXT"): ("v=spf1 include:sendgrid.com ~all",)})

    assert detect(await collect(resolver)) == []


class ExplodingResolver:
    """Answers one record type and raises for the rest."""

    def __init__(self, working_type: str, records: tuple[str, ...]) -> None:
        self._working_type = working_type
        self._records = records

    async def resolve(self, _name: str, record_type: str) -> DnsAnswer:
        if record_type != self._working_type:
            raise RuntimeError("resolver exploded")

        return DnsAnswer(records=self._records)


async def test_dns_collector_keeps_the_record_types_that_answered() -> None:
    """A resolver is contracted not to raise; one that does costs its own record type only."""
    resolver = ExplodingResolver("MX", ("10 aspmx.l.google.com.",))

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert detect(result.signals) == ["Google Workspace"]


async def test_dns_collector_reports_a_timed_out_record_type_as_a_failure() -> None:
    """No TXT answer within the budget is not the same as no TXT record, and must not read so."""
    resolver = FakeResolver({}, failures={(DOMAIN, "TXT"): FailureReasonEnum.TIMEOUT})

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert result.failure is not None
    assert result.failure.collector == "dns"
    assert result.failure.reason is FailureReasonEnum.TIMEOUT
    assert "TXT" in result.failure.detail


async def test_dns_collector_keeps_the_records_that_answered_beside_a_failure() -> None:
    resolver = FakeResolver(
        {(DOMAIN, "MX"): ("10 aspmx.l.google.com.",)},
        failures={(DOMAIN, "TXT"): FailureReasonEnum.TIMEOUT},
    )

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert detect(result.signals) == ["Google Workspace"]
    assert result.failure is not None


async def test_dns_collector_names_every_record_type_that_failed() -> None:
    resolver = FakeResolver(
        {},
        failures={
            (DOMAIN, "MX"): FailureReasonEnum.TIMEOUT,
            (DOMAIN, "TXT"): FailureReasonEnum.TIMEOUT,
        },
    )

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert result.failure is not None
    assert "MX" in result.failure.detail
    assert "TXT" in result.failure.detail
    assert "CNAME" not in result.failure.detail


async def test_dns_collector_reports_a_timeout_ahead_of_a_resolver_breakdown() -> None:
    """One failure per collector: the time-bound one is the actionable one."""
    resolver = FakeResolver(
        {},
        failures={
            (DOMAIN, "MX"): FailureReasonEnum.COLLECTOR_ERROR,
            (DOMAIN, "TXT"): FailureReasonEnum.TIMEOUT,
        },
    )

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert result.failure is not None
    assert result.failure.reason is FailureReasonEnum.TIMEOUT


async def test_dns_collector_describes_a_failure_reason_it_has_no_words_for() -> None:
    """The port admits every reason; one the registry does not name must still not raise."""
    resolver = FakeResolver({}, failures={(DOMAIN, "TXT"): FailureReasonEnum.DNS_UNRESOLVED})

    result = await DnsSignalCollector(resolver=resolver).collect(DOMAIN)

    assert result.failure is not None
    assert result.failure.reason is FailureReasonEnum.DNS_UNRESOLVED
    assert "TXT" in result.failure.detail
