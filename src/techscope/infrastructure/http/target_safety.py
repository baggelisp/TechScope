"""Deciding what this scanner is allowed to connect to, and to which address.

A scanner turns a name someone else chose into an outbound request from this host. Left
unchecked, that is a way to reach whatever this host can reach and nothing else can: a metadata
service on a link-local address, a database on a private network, a socket on loopback. The
domain need not even be suspicious — a redirect is enough, which is why every hop is checked and
not only the first.

Checking a name is not enough on its own, because a name is not what a socket connects to. Two
gaps close only by deciding here, once, and handing the decision to the caller:

* **The name must be encoded once.** ``str.encode("idna")`` implements IDNA 2003, which folds
  ``straße`` to ``strasse``; the ``idna`` package httpx uses implements IDNA 2008, which encodes
  it to ``xn--strae-oqa``. Resolve through one and connect through the other and an attacker who
  owns both names is checked on one and fetched on the other. So the host is encoded here, with
  the same library httpx uses, and every later step sees plain ASCII it cannot re-interpret.
* **The answer must not change underneath us.** Resolving here and letting the client resolve
  again leaves a window an authoritative server can drive: a public address for the check, a
  private one for the connection. So the approved addresses travel with the approval and the
  connection is pinned to them.

One address per family survives, in the order the resolver gave. That is what keeps a dual-stack
host reachable from a container with no IPv6 route, where pinning to a single answer would strand
the fetch.
"""

import asyncio
import logging
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
from socket import AF_UNSPEC, SOCK_STREAM
from urllib.parse import SplitResult, urlsplit, urlunsplit

import idna

from techscope.domain.enums import FailureReasonEnum

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORT_BY_SCHEME = {"http": 80, "https": 443}
IPV6_VERSION = 6
# The well-known prefix a NAT64 gateway maps IPv4 space into. Python reads such an address as
# global — it is, as a prefix — but the last 32 bits are an IPv4 address the gateway will forward
# to, and `64:ff9b::7f00:1` forwards to 127.0.0.1.
NAT64_NETWORK = IPv6Network("64:ff9b::/96")
NAT64_EMBEDDED_OFFSET = 32


@dataclass(frozen=True, slots=True)
class TargetRefusal:
    """Why a URL was not fetched, in the same vocabulary the rest of a failure uses."""

    reason: FailureReasonEnum
    detail: str


@dataclass(frozen=True, slots=True)
class ApprovedTarget:
    """A URL that may be fetched, and the addresses it was approved against."""

    # The URL as written, with the host in the ASCII form both the resolver and the client saw.
    url: str
    # Public addresses this name resolved to, at most one per family, in resolver order.
    addresses: tuple[str, ...]


async def decide_target(url: str) -> ApprovedTarget | TargetRefusal:
    """Approve this URL and say where to connect, or say why it is refused. Never raises."""
    parts = _split_or_none(url)

    if parts is None:
        return TargetRefusal(
            reason=FailureReasonEnum.INVALID_HOST, detail=f"{url!r} is not a usable URL"
        )

    if parts.scheme not in ALLOWED_SCHEMES:
        return TargetRefusal(
            reason=FailureReasonEnum.INVALID_HOST,
            detail=f"scheme {parts.scheme!r} is not http or https",
        )

    if parts.hostname is None or len(parts.hostname) == 0:
        return TargetRefusal(reason=FailureReasonEnum.INVALID_HOST, detail=f"{url!r} names no host")

    encoded_host = _encode_host_or_none(parts.hostname)

    if encoded_host is None:
        return TargetRefusal(
            reason=FailureReasonEnum.INVALID_HOST,
            detail=f"{parts.hostname!r} is not a usable host name",
        )

    port = _decide_port_or_none(parts)

    if port is None:
        return TargetRefusal(
            reason=FailureReasonEnum.INVALID_HOST, detail=f"{url!r} names no usable port"
        )

    addresses = await _resolve_or_none(encoded_host, port)

    if addresses is None:
        return TargetRefusal(
            reason=FailureReasonEnum.DNS_UNRESOLVED, detail=f"{encoded_host} does not resolve"
        )

    refusal = _decide_private_refusal_or_none(encoded_host, addresses)

    if refusal is not None:
        return refusal

    return ApprovedTarget(
        url=_rebuild_url(parts, encoded_host, port),
        addresses=_pick_one_address_per_family(addresses),
    )


def _encode_host_or_none(host: str) -> str | None:
    """The one place a host becomes bytes on the wire.

    An address literal is left as it is. A name goes through the same call httpx makes, so
    neither the resolver nor the client is ever left to guess which name this was.
    """
    try:
        ip_address(host)
    except ValueError:
        return _encode_name_or_none(host)

    return host


def _encode_name_or_none(host: str) -> str | None:
    lowered = host.lower()

    if lowered.isascii():
        return lowered

    try:
        return idna.encode(lowered).decode("ascii")
    except idna.IDNAError as error:
        logger.debug("cannot encode host %r: %s", host, error)

        return None


def _rebuild_url(parts: SplitResult, host: str, port: int) -> str:
    """The URL as given, with the host replaced by its wire form and any userinfo dropped."""
    return urlunsplit(
        (parts.scheme, _build_authority(host, port, parts.scheme), parts.path, parts.query, "")
    )


def _build_authority(host: str, port: int, scheme: str) -> str:
    written_host = _write_host(host)

    if port == DEFAULT_PORT_BY_SCHEME[scheme]:
        return written_host

    return f"{written_host}:{port}"


def _write_host(host: str) -> str:
    """An IPv6 literal is written in brackets; anything else is written as it is."""
    try:
        parsed = ip_address(host)
    except ValueError:
        return host

    if parsed.version == IPV6_VERSION:
        return f"[{host}]"

    return host


def _split_or_none(url: str) -> SplitResult | None:
    """A redirect writes this, so it is not a URL until it parses as one."""
    try:
        return urlsplit(url)
    except ValueError as error:
        logger.debug("cannot parse %r: %s", url, error)

        return None


def _decide_port_or_none(parts: SplitResult) -> int | None:
    """`urlsplit` accepts any digits; reading the port is where a number out of range is refused."""
    try:
        written_port = parts.port
    except ValueError as error:
        logger.debug("cannot read the port of %r: %s", parts.geturl(), error)

        return None

    if written_port is not None:
        return written_port

    return DEFAULT_PORT_BY_SCHEME[parts.scheme]


async def _resolve_or_none(host: str, port: int) -> list[str] | None:
    loop = asyncio.get_running_loop()

    try:
        answers = await loop.getaddrinfo(host, port, family=AF_UNSPEC, type=SOCK_STREAM)
    except OSError as error:
        logger.debug("cannot resolve %s: %s", host, error)

        return None

    if len(answers) == 0:
        return None

    return [str(answer[4][0]) for answer in answers]


def _pick_one_address_per_family(addresses: list[str]) -> tuple[str, ...]:
    """Enough to survive a host whose preferred family this machine cannot route."""
    chosen: list[str] = []
    seen_versions: set[int] = set()

    for address in addresses:
        version = ip_address(address).version

        if version in seen_versions:
            continue

        seen_versions.add(version)
        chosen.append(address)

    return tuple(chosen)


def _decide_private_refusal_or_none(host: str, addresses: list[str]) -> TargetRefusal | None:
    """Every address must be public: one private answer is enough to refuse the name."""
    for address in addresses:
        if not is_public_address(address):
            return TargetRefusal(
                reason=FailureReasonEnum.PRIVATE_TARGET,
                detail=f"{host} resolves to {address}, which is not a public address",
            )

    return None


def is_public_address(address: str) -> bool:
    """Public means routable on the internet, which multicast is not despite being global.

    Anything that is not an address at all answers ``False``: this is asked about values that
    came from outside, and the safe answer to "is this safe" is never "it is not a question".
    """
    try:
        parsed = ip_address(address)
    except ValueError:
        return False

    if not parsed.is_global:
        return False

    if parsed.is_multicast:
        return False

    embedded = _decide_embedded_ipv4_or_none(parsed)

    if embedded is None:
        return True

    return is_public_address(str(embedded))


def _decide_embedded_ipv4_or_none(parsed: IPv4Address | IPv6Address) -> IPv4Address | None:
    """The IPv4 address a NAT64 gateway would forward to, when this is one of those.

    Python already reads the IPv4-mapped, 6to4 and Teredo forms as non-global; the well-known
    NAT64 prefix is the one it cannot, because the prefix really is globally routed.
    """
    if not isinstance(parsed, IPv6Address):
        return None

    if parsed not in NAT64_NETWORK:
        return None

    return IPv4Address(int(parsed) & 0xFFFFFFFF)
