"""Looking up DNS records, bounded and non-raising.

A name that does not exist and a record type that is not published are answers: no records,
and nothing went wrong, because an absent MX record is information too. A resolver that did not
answer in time is not an answer. It comes back as no records *and* a failure, so the scan can
say that the records were never read rather than that they do not exist.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

import dns.asyncresolver
import dns.exception
import dns.rdata
import dns.rdtypes.ANY.TXT
import dns.resolver

from techscope.domain.enums import FailureReasonEnum

logger = logging.getLogger(__name__)

# One nameserver attempt, and the whole lookup. Separating them matters: a large TXT answer is
# truncated over UDP and has to be retried over TCP, and a single budget lets one slow nameserver
# eat it all before the retry can happen. The attempt bound is what abandons that nameserver; the
# lifetime has to be long enough for the retry to then succeed. Measured over repeated lookups of
# domains whose records dig confirms: 1 s / 3 s left 4 of 15 answers empty, every failure landing
# exactly on the lifetime. 1 s / 5 s left none empty, worst case 3.7 s.
ATTEMPT_TIMEOUT_SECONDS = 1.0
RECORD_TIMEOUT_SECONDS = 5.0

# How many lookups this scanner will have in flight at once, across every domain. Scanning 20
# domains ten at a time means thirty simultaneous queries, and a resolver asked for thirty at
# once starts dropping them: measured over the assignment's domains, an unbounded burst returned
# 661-676 records and a different number on each run, while a bound of ten returned 749 every
# time and did it faster. This is the scanner being a polite client of its own resolver.
MAXIMUM_CONCURRENT_LOOKUPS = 10
TXT_STRING_ENCODING = "utf-8"
TXT_DECODE_ERROR_POLICY = "replace"

# The ordinary ways a lookup comes back with nothing to say. Everything else did not finish.
ABSENT_RECORD_ERRORS = (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer)


@dataclass(frozen=True, slots=True)
class DnsAnswer:
    """What one lookup produced, and whether it actually finished.

    Empty records with no failure mean the name publishes nothing of that type. Empty records
    with a failure mean nothing is known: a lookup that timed out has not said "no TXT record",
    and a scan that reads it that way silently loses every detection those records carry.
    """

    records: tuple[str, ...]
    failure: FailureReasonEnum | None = None


class Resolver(Protocol):
    """Answers one record type for one name. Never raises: a problem comes back on the answer."""

    async def resolve(self, name: str, record_type: str) -> DnsAnswer: ...


def build_async_resolver(nameservers: tuple[str, ...] = ()) -> dns.asyncresolver.Resolver:
    """The resolver this adapter expects, configured once.

    The module-level convenience function re-reads the system configuration on every call, and
    leaves the per-attempt bound at its default, which is what starved the TCP retry.

    Given no nameservers, the system's are used. Given some, they replace them: measured over
    three full runs of the assignment's domains, the system resolver on one machine returned
    713-749 records and a different number each time, while a public one returned 749 every time
    and fifteen times faster. Which to trust is the caller's decision, not this module's.
    """
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = ATTEMPT_TIMEOUT_SECONDS
    resolver.lifetime = RECORD_TIMEOUT_SECONDS

    if len(nameservers) > 0:
        resolver.nameservers = list(nameservers)

    return resolver


class DnsPythonResolver:
    """The real resolver, bounded per attempt and per record type."""

    def __init__(self, resolver: dns.asyncresolver.Resolver) -> None:
        self._resolver = resolver
        self._in_flight = asyncio.Semaphore(MAXIMUM_CONCURRENT_LOOKUPS)

    async def resolve(self, name: str, record_type: str) -> DnsAnswer:
        async with self._in_flight:
            return await self._resolve_now(name, record_type)

    async def _resolve_now(self, name: str, record_type: str) -> DnsAnswer:
        try:
            answer = await self._resolver.resolve(name, record_type)
        except ABSENT_RECORD_ERRORS as error:
            logger.debug("%s has no %s record: %s", name, record_type, type(error).__name__)

            return DnsAnswer(records=())
        except dns.exception.Timeout:
            logger.debug(
                "%s %s lookup timed out after %.1fs", name, record_type, RECORD_TIMEOUT_SECONDS
            )

            return DnsAnswer(records=(), failure=FailureReasonEnum.TIMEOUT)
        except dns.exception.DNSException as error:
            logger.warning("%s %s lookup failed: %r", name, record_type, error)

            return DnsAnswer(records=(), failure=FailureReasonEnum.COLLECTOR_ERROR)

        return DnsAnswer(records=tuple(_decide_record_text(record) for record in answer))


def _decide_record_text(record: dns.rdata.Rdata) -> str:
    """A TXT record's strings are joined: a long SPF record is split at 255 bytes.

    Leaving them apart would let a pattern fall into the seam, so they are concatenated the way
    a resolver client is meant to read them.
    """
    if isinstance(record, dns.rdtypes.ANY.TXT.TXT):
        return "".join(
            part.decode(TXT_STRING_ENCODING, errors=TXT_DECODE_ERROR_POLICY)
            for part in record.strings
        )

    return record.to_text()
