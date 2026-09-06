"""Guards that hold for every unit test.

`respx` keeps HTTP off the network, but it knows nothing about name resolution: a test that drives
the whole CLI would otherwise query real nameservers, which is how a DNS lookup for stripe.com once
turned up inside a test asserting an empty result. Patching the resolver class rather than one
module's reference to it means no unit test can reach a nameserver by any route; a test that
wants DNS answers substitutes its own resolver instance, which still shadows this.

Two routes leave this process, and both are closed here. dnspython carries the record lookups;
``getaddrinfo`` carries the one the SSRF guard makes before every fetch, and that one runs even in
a test whose HTTP is entirely mocked.
"""

import asyncio
import socket
from collections.abc import Sequence
from ipaddress import ip_address

import dns.asyncresolver
import dns.rdata
import dns.resolver
import pytest

# Any name a test does not say more about resolves here: a public address, so the guard allows it.
PUBLIC_TEST_ADDRESS = "93.184.216.34"
# The suffix RFC 2606 reserves for names that are guaranteed not to resolve.
UNRESOLVABLE_SUFFIX = ".invalid"
IPV6_VERSION = 6

AddressInfo = tuple[int, int, int, str, tuple[str, int] | tuple[str, int, int, int]]


@pytest.fixture(autouse=True)
def block_real_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(*_args: object, **_keywords: object) -> Sequence[dns.rdata.Rdata]:
        raise dns.resolver.NoAnswer

    monkeypatch.setattr(dns.asyncresolver.Resolver, "resolve", refuse)


@pytest.fixture
def dns_answers() -> dict[str, tuple[str, ...]]:
    """Names a test wants resolved its own way, for the tests that are about resolution."""
    return {}


@pytest.fixture(autouse=True)
def block_real_hostname_lookups(
    monkeypatch: pytest.MonkeyPatch, dns_answers: dict[str, tuple[str, ...]]
) -> None:
    """Every name resolves to one public address; an address literal resolves to itself."""

    async def resolve(
        _loop: object, host: str, port: int, **_keywords: object
    ) -> list[AddressInfo]:
        if host.endswith(UNRESOLVABLE_SUFFIX):
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

        addresses = dns_answers.get(host, decide_test_addresses(host))

        return [build_address_info(address, port) for address in addresses]

    monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "getaddrinfo", resolve)


def decide_test_addresses(host: str) -> tuple[str, ...]:
    try:
        ip_address(host)
    except ValueError:
        return (PUBLIC_TEST_ADDRESS,)

    return (host,)


def build_address_info(address: str, port: int) -> AddressInfo:
    parsed = ip_address(address)

    if parsed.version == IPV6_VERSION:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))

    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
