"""The real resolver adapter: turning dnspython's answers and refusals into plain strings.

dnspython has no purpose-built mock the way httpx has respx, so the adapter is given a real
resolver object whose one network call is substituted. Nothing here reaches a nameserver.
"""

import asyncio
from collections.abc import Sequence

import dns.exception
import dns.name
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.MX
import dns.rdtypes.ANY.TXT
import dns.resolver
import pytest

from techscope.infrastructure.dns.resolver import (
    MAXIMUM_CONCURRENT_LOOKUPS,
    DnsPythonResolver,
    build_async_resolver,
)

NAME = "example.com"


def build_text_record(*parts: bytes) -> dns.rdtypes.ANY.TXT.TXT:
    return dns.rdtypes.ANY.TXT.TXT(dns.rdataclass.IN, dns.rdatatype.TXT, list(parts))


def build_mail_record(preference: int, exchange: str) -> dns.rdtypes.ANY.MX.MX:
    return dns.rdtypes.ANY.MX.MX(
        dns.rdataclass.IN, dns.rdatatype.MX, preference, dns.name.from_text(exchange)
    )


def build_answering_resolver(
    monkeypatch: pytest.MonkeyPatch, records: Sequence[dns.rdata.Rdata]
) -> DnsPythonResolver:
    underlying = build_async_resolver()

    async def resolve(*_args: object, **_keywords: object) -> Sequence[dns.rdata.Rdata]:
        return records

    monkeypatch.setattr(underlying, "resolve", resolve)

    return DnsPythonResolver(underlying)


def build_refusing_resolver(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> DnsPythonResolver:
    underlying = build_async_resolver()

    async def resolve(*_args: object, **_keywords: object) -> Sequence[dns.rdata.Rdata]:
        raise error

    monkeypatch.setattr(underlying, "resolve", resolve)

    return DnsPythonResolver(underlying)


def test_build_async_resolver_bounds_one_attempt_more_tightly_than_the_whole_lookup() -> None:
    """The bug this separation fixes: one slow nameserver used to eat the entire budget.

    A large TXT answer is truncated over UDP and retried over TCP. With a single bound, a
    nameserver that never answers consumed it before the retry could run, and every TXT lookup
    came back empty.
    """
    resolver = build_async_resolver()

    assert resolver.timeout < resolver.lifetime


async def test_resolver_returns_a_mail_record_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = build_answering_resolver(monkeypatch, [build_mail_record(10, "aspmx.l.google.com.")])

    assert await resolver.resolve(NAME, "MX") == ("10 aspmx.l.google.com.",)


async def test_resolver_returns_every_record(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = build_answering_resolver(
        monkeypatch,
        [build_mail_record(10, "aspmx.l.google.com."), build_mail_record(20, "alt.google.com.")],
    )

    assert len(await resolver.resolve(NAME, "MX")) == 2


async def test_resolver_joins_the_strings_of_a_split_text_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A long SPF record is split at 255 bytes; a pattern must not fall into the seam."""
    resolver = build_answering_resolver(
        monkeypatch, [build_text_record(b"v=spf1 include:send", b"grid.net ~all")]
    )

    assert await resolver.resolve(NAME, "TXT") == ("v=spf1 include:sendgrid.net ~all",)


async def test_resolver_returns_a_single_string_text_record_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = build_answering_resolver(
        monkeypatch, [build_text_record(b"hubspot-developer-verification=abc")]
    )

    assert await resolver.resolve(NAME, "TXT") == ("hubspot-developer-verification=abc",)


async def test_resolver_replaces_undecodable_bytes_in_a_text_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = build_answering_resolver(monkeypatch, [build_text_record(b"prefix-\xff\xfe-suffix")])

    records = await resolver.resolve(NAME, "TXT")

    assert "prefix-" in records[0]
    assert "-suffix" in records[0]


@pytest.mark.parametrize(
    "error",
    [
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ],
    ids=["no such domain", "no record of this type", "no nameserver answered", "timed out"],
)
async def test_resolver_reports_no_records_for_an_ordinary_absence(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    resolver = build_refusing_resolver(monkeypatch, error)

    assert await resolver.resolve(NAME, "MX") == ()


async def test_resolver_reports_no_records_for_an_unexpected_dns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A collector never raises: an unusable resolver is an empty answer with a warning."""
    resolver = build_refusing_resolver(monkeypatch, dns.exception.FormError)

    assert await resolver.resolve(NAME, "MX") == ()


async def test_resolver_of_an_empty_answer_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = build_answering_resolver(monkeypatch, [])

    assert await resolver.resolve(NAME, "CNAME") == ()


class LookupCounter:
    """Counts how many lookups the adapter has running at once."""

    def __init__(self) -> None:
        self.peak = 0
        self._in_flight = 0

    async def resolve(self, *_args: object, **_keywords: object) -> Sequence[dns.rdata.Rdata]:
        self._in_flight += 1
        self.peak = max(self.peak, self._in_flight)
        await asyncio.sleep(0.01)
        self._in_flight -= 1

        return []


async def test_resolver_bounds_how_many_lookups_it_has_in_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolver asked for thirty queries at once starts dropping them."""
    counter = LookupCounter()
    underlying = build_async_resolver()
    monkeypatch.setattr(underlying, "resolve", counter.resolve)
    resolver = DnsPythonResolver(underlying)

    requested = MAXIMUM_CONCURRENT_LOOKUPS * 4
    await asyncio.gather(*(resolver.resolve(NAME, "MX") for _ in range(requested)))

    assert counter.peak == MAXIMUM_CONCURRENT_LOOKUPS
