"""The two ways a checked name and a connected address can drift apart.

Both were found by a security review of the guard added in this feature, and both are the same
mistake in different clothes: the check describes something the connection is not bound to. One
lets two libraries disagree about which name was written; the other lets a nameserver change its
mind between the check and the socket.
"""

import asyncio
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

import httpcore
import httpx
import pytest
import respx

from techscope.domain.enums import FailureReasonEnum
from techscope.infrastructure.http import homepage_fetcher
from techscope.infrastructure.http.models import FetchFailure
from techscope.infrastructure.http.pinned_address import (
    PinnedAddressBackend,
    build_pinned_transport,
    connecting_only_to,
)
from techscope.infrastructure.http.target_safety import (
    ApprovedTarget,
    TargetRefusal,
    decide_target,
    is_public_address,
)

HTTPS_URL = "https://example.com/"
PUBLIC_ADDRESS = "93.184.216.34"
OTHER_PUBLIC_ADDRESS = "93.184.216.35"
PUBLIC_IPV6_ADDRESS = "2606:2800:220:1:248:1893:25c8:1946"


def expect_approval(decision: ApprovedTarget | TargetRefusal) -> ApprovedTarget:
    assert isinstance(decision, ApprovedTarget), decision

    return decision


def expect_refusal(decision: ApprovedTarget | TargetRefusal) -> TargetRefusal:
    assert isinstance(decision, TargetRefusal), decision

    return decision


class RecordingBackend(httpcore.AsyncNetworkBackend):
    """Stands in for the real network, remembering what it was asked to connect to."""

    def __init__(self, refusing: tuple[str, ...] = ()) -> None:
        self.connected: list[str] = []
        self._refusing = refusing

    async def connect_tcp(
        self,
        host: str,
        port: int,  # noqa: ARG002
        timeout: float | None = None,  # noqa: ARG002
        local_address: str | None = None,  # noqa: ARG002
        socket_options: Iterable[object] | None = None,  # noqa: ARG002
    ) -> httpcore.AsyncNetworkStream:
        self.connected.append(host)

        if host in self._refusing:
            raise httpcore.ConnectError(f"no route to {host}")

        return httpcore.AsyncNetworkStream()


class FakeNetworkStream:
    """Only the one question the peer audit asks of a real stream."""

    def __init__(self, server_address: tuple[str, int]) -> None:
        self._server_address = server_address

    def get_extra_info(self, name: str) -> tuple[str, int] | None:
        if name == "server_addr":
            return self._server_address

        return None


# --- The name must be encoded once ------------------------------------------------------------


async def test_a_unicode_host_is_encoded_the_way_the_http_client_encodes_it() -> None:
    """`straße` is `xn--strae-oqa` under IDNA 2008 and `strasse` under the IDNA 2003 of `socket`.

    Approving one name and fetching the other is the whole bypass, so the approved URL must carry
    the form the client will use and must never carry the folded one.
    """
    # The divergence itself, so this test fails loudly if it ever stops existing.
    assert "straße.de".encode("idna").decode("ascii") == "strasse.de"

    approved = expect_approval(await decide_target("https://straße.de/"))

    assert "xn--strae-oqa.de" in approved.url
    assert "strasse.de" not in approved.url


async def test_the_approved_url_leaves_nothing_left_to_encode() -> None:
    """Pure ASCII is the only form no second library can interpret differently."""
    approved = expect_approval(await decide_target("https://münchen.de/preise"))

    assert approved.url.isascii()
    assert approved.url == "https://xn--mnchen-3ya.de/preise"


async def test_a_host_that_is_not_a_name_is_refused_rather_than_resolved() -> None:
    decision = expect_refusal(await decide_target("https://\U0001f600.com/"))

    assert decision.reason is FailureReasonEnum.INVALID_HOST


async def test_credentials_in_a_redirect_are_dropped_from_the_approved_url() -> None:
    """A redirect can write anything into the authority; only the host survives the guard."""
    approved = expect_approval(await decide_target("https://user:secret@example.com/"))

    assert approved.url == HTTPS_URL
    assert "secret" not in approved.url


async def test_a_non_default_port_survives_the_rebuild() -> None:
    approved = expect_approval(await decide_target("https://example.com:8443/here?q=1"))

    assert approved.url == "https://example.com:8443/here?q=1"


async def test_an_ipv6_literal_keeps_its_brackets() -> None:
    approved = expect_approval(await decide_target(f"https://[{PUBLIC_IPV6_ADDRESS}]/"))

    assert approved.url == f"https://[{PUBLIC_IPV6_ADDRESS}]/"
    assert approved.addresses == (PUBLIC_IPV6_ADDRESS,)


# --- The answer must not change underneath us ---------------------------------------------------


async def test_the_approval_carries_the_addresses_it_was_granted_against(
    dns_answers: dict[str, tuple[str, ...]],
) -> None:
    dns_answers["example.com"] = (PUBLIC_ADDRESS,)

    approved = expect_approval(await decide_target(HTTPS_URL))

    assert approved.addresses == (PUBLIC_ADDRESS,)


async def test_one_address_of_each_family_is_approved(
    dns_answers: dict[str, tuple[str, ...]],
) -> None:
    """Enough to survive a family this machine cannot route, and no more connect attempts."""
    dns_answers["example.com"] = (
        PUBLIC_IPV6_ADDRESS,
        PUBLIC_ADDRESS,
        OTHER_PUBLIC_ADDRESS,
    )

    approved = expect_approval(await decide_target(HTTPS_URL))

    assert approved.addresses == (PUBLIC_IPV6_ADDRESS, PUBLIC_ADDRESS)


async def test_one_private_answer_refuses_the_whole_name(
    dns_answers: dict[str, tuple[str, ...]],
) -> None:
    dns_answers["example.com"] = (PUBLIC_ADDRESS, "169.254.169.254")

    decision = expect_refusal(await decide_target(HTTPS_URL))

    assert decision.reason is FailureReasonEnum.PRIVATE_TARGET


async def test_a_nameserver_that_changes_its_answer_cannot_move_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rebinding attack, start to finish: public to the check, loopback to the connection.

    Nothing resolves the name a second time, so the second answer has nowhere to land.
    """
    answers = iter([(PUBLIC_ADDRESS,), ("127.0.0.1",)])

    async def flip(_loop: object, _host: str, port: int, **_keywords: object) -> list[object]:
        return [(2, 1, 6, "", (next(answers)[0], port))]

    monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "getaddrinfo", flip)

    approved = expect_approval(await decide_target(HTTPS_URL))
    inner = RecordingBackend()
    backend = PinnedAddressBackend(inner)

    with connecting_only_to(approved.addresses):
        await backend.connect_tcp("example.com", 443)

    assert inner.connected == [PUBLIC_ADDRESS]
    # The second answer is still waiting, unused: nothing ever asked again.
    assert next(answers) == ("127.0.0.1",)


async def test_the_backend_connects_to_the_approved_address_and_not_to_the_name() -> None:
    inner = RecordingBackend()
    backend = PinnedAddressBackend(inner)

    with connecting_only_to((PUBLIC_ADDRESS,)):
        await backend.connect_tcp("example.com", 443)

    assert inner.connected == [PUBLIC_ADDRESS]


async def test_the_backend_refuses_to_connect_when_nothing_was_approved() -> None:
    """The guarantee this is here for: no socket without a verdict behind it."""
    inner = RecordingBackend()
    backend = PinnedAddressBackend(inner)

    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("example.com", 443)

    assert inner.connected == []


async def test_the_backend_tries_the_next_family_when_the_first_is_unroutable() -> None:
    """A container with no IPv6 route must still reach a dual-stack host."""
    inner = RecordingBackend(refusing=(PUBLIC_IPV6_ADDRESS,))
    backend = PinnedAddressBackend(inner)

    with connecting_only_to((PUBLIC_IPV6_ADDRESS, PUBLIC_ADDRESS)):
        await backend.connect_tcp("example.com", 443)

    assert inner.connected == [PUBLIC_IPV6_ADDRESS, PUBLIC_ADDRESS]


async def test_the_backend_names_every_address_it_could_not_reach() -> None:
    inner = RecordingBackend(refusing=(PUBLIC_ADDRESS, OTHER_PUBLIC_ADDRESS))
    backend = PinnedAddressBackend(inner)

    with (
        connecting_only_to((PUBLIC_ADDRESS, OTHER_PUBLIC_ADDRESS)),
        pytest.raises(httpcore.ConnectError) as raised,
    ):
        await backend.connect_tcp("example.com", 443)

    assert PUBLIC_ADDRESS in str(raised.value)
    assert OTHER_PUBLIC_ADDRESS in str(raised.value)


async def test_the_backend_refuses_a_unix_socket() -> None:
    backend = PinnedAddressBackend(RecordingBackend())

    with pytest.raises(httpcore.ConnectError):
        await backend.connect_unix_socket("/var/run/docker.sock")


async def test_an_approval_does_not_leak_between_domains_scanned_at_the_same_time() -> None:
    """Twenty domains are in flight at once; each connection must see only its own verdict."""
    inner = RecordingBackend()
    backend = PinnedAddressBackend(inner)

    async def connect(address: str) -> None:
        with connecting_only_to((address,)):
            await asyncio.sleep(0)
            await backend.connect_tcp("example.com", 443)

    await asyncio.gather(connect(PUBLIC_ADDRESS), connect(OTHER_PUBLIC_ADDRESS))

    assert sorted(inner.connected) == sorted([PUBLIC_ADDRESS, OTHER_PUBLIC_ADDRESS])


def test_the_client_transport_pins_every_connection_it_makes() -> None:
    """The wiring itself, because a guard that is not installed is not a guard."""
    transport = build_pinned_transport()

    assert isinstance(transport._pool._network_backend, PinnedAddressBackend)


# --- The audit that does not share the control's failure mode -----------------------------------


@respx.mock
async def test_a_response_that_arrived_from_a_private_address_is_dropped() -> None:
    """If the pinning were ever to stop applying, this is what still notices."""
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            text="internal",
            extensions={"network_stream": FakeNetworkStream(("169.254.169.254", 443))},
        )
    )

    async with homepage_fetcher.build_client() as client:
        fetcher = homepage_fetcher.HomepageFetcher(
            client=client, retry_backoff_seconds=0.0, total_timeout_seconds=5.0
        )
        result = await fetcher.fetch("example.com")

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.PRIVATE_TARGET


@respx.mock
async def test_a_response_from_a_public_address_is_kept() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            text="<html></html>",
            extensions={"network_stream": FakeNetworkStream((PUBLIC_ADDRESS, 443))},
        )
    )

    async with homepage_fetcher.build_client() as client:
        fetcher = homepage_fetcher.HomepageFetcher(
            client=client, retry_backoff_seconds=0.0, total_timeout_seconds=5.0
        )
        result = await fetcher.fetch("example.com")

    assert not isinstance(result, FetchFailure)


# --- The fetcher hands the verdict to the connection --------------------------------------------


@respx.mock
async def test_the_fetcher_approves_the_addresses_before_it_asks_for_the_page(
    monkeypatch: pytest.MonkeyPatch, dns_answers: dict[str, tuple[str, ...]]
) -> None:
    dns_answers["example.com"] = (PUBLIC_ADDRESS,)
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text="<html></html>"))
    approvals: list[tuple[str, ...]] = []

    @contextmanager
    def record(addresses: tuple[str, ...]) -> Iterator[None]:
        approvals.append(addresses)

        yield

    monkeypatch.setattr(homepage_fetcher, "connecting_only_to", record)

    async with homepage_fetcher.build_client() as client:
        fetcher = homepage_fetcher.HomepageFetcher(
            client=client, retry_backoff_seconds=0.0, total_timeout_seconds=5.0
        )
        await fetcher.fetch("example.com")

    assert approvals == [(PUBLIC_ADDRESS,)]


# --- Nothing here may raise: a redirect writes these, and the fetcher promises never to raise ----


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example:99999/",
        "http://evil.example:-1/",
        "https://example.com:port/",
    ],
    ids=["a port above the range", "a negative port", "a port that is not a number"],
)
async def test_an_unusable_port_is_refused_rather_than_raised(url: str) -> None:
    decision = expect_refusal(await decide_target(url))

    assert decision.reason is FailureReasonEnum.INVALID_HOST


@respx.mock
async def test_a_redirect_to_an_unusable_port_is_reported_honestly() -> None:
    """It reaches the guard through a header, so it comes back as a failure, never as a raise."""
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(302, headers={"location": "http://evil.example:99999/"})
    )

    async with homepage_fetcher.build_client() as client:
        fetcher = homepage_fetcher.HomepageFetcher(
            client=client, retry_backoff_seconds=0.0, total_timeout_seconds=5.0
        )
        result = await fetcher.fetch("example.com")

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.INVALID_HOST


@pytest.mark.parametrize(
    "address",
    ["/var/run/docker.sock", "", "not-an-address"],
    ids=["a unix socket path", "nothing", "a name"],
)
def test_something_that_is_not_an_address_is_not_a_public_address(address: str) -> None:
    """Asked about a value from outside, the safe answer is never that it is not a question."""
    assert not is_public_address(address)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("64:ff9b::7f00:1", False),
        ("64:ff9b::a00:1", False),
        ("64:ff9b::808:808", True),
        ("2606:4700::1", True),
    ],
    ids=["NAT64 to loopback", "NAT64 to a private network", "NAT64 to a public host", "ordinary"],
)
def test_an_address_a_gateway_would_translate_is_judged_by_what_it_translates_to(
    address: str, expected: bool
) -> None:
    """Python reads the NAT64 prefix as global, because as a prefix it is."""
    assert is_public_address(address) is expected


# --- The substitution really happens, through real httpx and a real socket --------------------


async def test_a_request_reaches_the_pinned_address_through_the_real_client() -> None:
    """No mock anywhere below the client: this is the only test that proves the wiring works.

    The server is on loopback and nothing leaves this machine; what is exercised is that httpx,
    told to fetch a name, opens its socket to the address the approval named instead.
    """
    served: list[bytes] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        served.append(await reader.read(1024))
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async with server, homepage_fetcher.build_client() as client:
        with connecting_only_to(("127.0.0.1",)):
            response = await client.get(f"http://pinned.example:{port}/")

    assert response.status_code == 200
    assert response.text == "hi"
    # The name went out in the request; only the socket knew about the address.
    assert b"host: pinned.example" in served[0].lower()


async def test_the_real_client_will_not_connect_without_an_approval() -> None:
    """The same client, the same server, no approval in scope."""

    async def handle(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async with server, homepage_fetcher.build_client() as client:
        with pytest.raises(httpx.ConnectError):
            await client.get(f"http://pinned.example:{port}/")
