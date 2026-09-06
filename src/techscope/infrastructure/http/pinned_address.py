"""Connecting to the address the guard approved, rather than to whatever DNS says next.

The guard in ``target_safety`` resolves a name and refuses it if any answer is not public. If the
client then resolves the same name again, that verdict describes an answer nobody is bound to: an
authoritative server that returns a public address to the first query and a private one to the
second walks straight past the check. The window is small and entirely under the attacker's
control, which is what makes it worth closing.

The substitution happens at the last possible moment — where a name becomes a socket — because
that is the only place it costs nothing else. Rewriting the URL instead would work, but the URL
is what the ``Host`` header, the certificate check, the connection pool and this scanner's own
output are all derived from, and every one of them would then need the name handed back to it.
Down here the name survives untouched and only the connection changes.

Which addresses are approved is per request, so it travels in a context variable rather than a
map on this object: nothing is shared between two domains being scanned at the same time, and
nothing outlives the request that set it.

What this binds is the moment a connection is *made*. A pooled connection that is handed
back out later is not re-approved, and does not need to be: it is still the socket that was
opened to an approved address, and the pool only ever reuses one for the identical origin. The
guarantee is therefore "no new socket without a verdict", not "no byte without a verdict" — worth
knowing before feature 11 holds a pool across domains a stranger supplied.

One connection failure moves on to the next approved address. That is what keeps a dual-stack
host reachable from a container with no IPv6 route, where committing to a single answer would
strand the fetch.
"""

import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import httpcore
import httpx
from httpcore import SOCKET_OPTION

logger = logging.getLogger(__name__)

# Empty means no target has been approved, which is the state in which nothing may be connected to.
_approved_addresses: ContextVar[tuple[str, ...]] = ContextVar(
    "techscope_approved_addresses", default=()
)


@contextmanager
def connecting_only_to(addresses: tuple[str, ...]) -> Iterator[None]:
    """Inside this block, a connection may go to these addresses and to nothing else."""
    token = _approved_addresses.set(addresses)

    try:
        yield
    finally:
        _approved_addresses.reset(token)


class PinnedAddressBackend(httpcore.AsyncNetworkBackend):
    """Substitutes an approved address for the host name, and refuses when there is none."""

    def __init__(self, inner: httpcore.AsyncNetworkBackend) -> None:
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = _approved_addresses.get()

        if len(addresses) == 0:
            raise httpcore.ConnectError(
                f"refusing to connect to {host}: no address was approved for this request"
            )

        return await self._connect_to_first_reachable(
            host, port, addresses, timeout, local_address, socket_options
        )

    async def _connect_to_first_reachable(
        self,
        host: str,
        port: int,
        addresses: tuple[str, ...],
        timeout: float | None,
        local_address: str | None,
        socket_options: Iterable[SOCKET_OPTION] | None,
    ) -> httpcore.AsyncNetworkStream:
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None

        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                logger.debug("%s is not reachable at %s: %s", host, address, error)
                last_error = error

        raise _describe_unreachable(host, addresses, last_error)

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ARG002
        socket_options: Iterable[SOCKET_OPTION] | None = None,  # noqa: ARG002
    ) -> httpcore.AsyncNetworkStream:
        """A unix socket is not an address this scanner has any business reaching."""
        raise httpcore.ConnectError(f"refusing to connect to the unix socket {path}")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def build_pinned_transport() -> httpx.AsyncHTTPTransport:
    """An ordinary httpx transport whose connections go only where the guard allowed."""
    transport = httpx.AsyncHTTPTransport()
    pool = transport._pool
    inner = pool._network_backend

    if not isinstance(inner, httpcore.AsyncNetworkBackend):
        raise RuntimeError(
            "httpx no longer exposes a network backend on its connection pool, so connections "
            "cannot be pinned to an approved address; the SSRF guard must not run without it"
        )

    pool._network_backend = PinnedAddressBackend(inner)

    return transport


def _describe_unreachable(
    host: str,
    addresses: tuple[str, ...],
    last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None,
) -> Exception:
    written = ", ".join(addresses)

    if last_error is None:
        return httpcore.ConnectError(f"no approved address for {host}")

    return type(last_error)(f"{host} refused a connection at {written}: {last_error}")
