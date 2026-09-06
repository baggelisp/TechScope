"""The DNS source of signals: mail, verification and alias records on the apex.

These are the signals a homepage cannot give. A mail exchanger names the mail provider, a TXT
record carries the verification tokens a vendor asks a customer to publish, and a CNAME names
whoever the domain points at.
"""

import asyncio
import logging
from dataclasses import dataclass

from techscope.application.ports.signal_collector import CollectionResult
from techscope.domain.domain_name import decide_apex_domain
from techscope.domain.enums import ChannelEnum, FailureReasonEnum
from techscope.domain.models import CollectionFailure, Signal
from techscope.infrastructure.dns.resolver import RECORD_TIMEOUT_SECONDS, DnsAnswer, Resolver

logger = logging.getLogger(__name__)

COLLECTOR_NAME = "dns"

# The one place a record type becomes a channel. Adding a type is an entry here.
CHANNEL_BY_RECORD_TYPE: dict[str, ChannelEnum] = {
    "MX": ChannelEnum.DNS_MX,
    "TXT": ChannelEnum.DNS_TXT,
    "CNAME": ChannelEnum.DNS_CNAME,
}

# How each way a lookup can fail reads in the details file. The port admits every reason, so
# one not named here reads as the plain default rather than raising inside a collector.
DETAIL_BY_FAILURE_REASON: dict[FailureReasonEnum, str] = {
    FailureReasonEnum.TIMEOUT: f"timed out after {RECORD_TIMEOUT_SECONDS:.0f}s",
    FailureReasonEnum.COLLECTOR_ERROR: "failed",
}
DEFAULT_FAILURE_DETAIL = "failed"


@dataclass(frozen=True, slots=True)
class _FailedLookup:
    """One record type whose lookup did not finish, and why."""

    record_type: str
    reason: FailureReasonEnum


class DnsSignalCollector:
    """Queries every record type concurrently and turns the answers into signals.

    A record type whose lookup did not finish is reported as a failure beside whatever the
    other types returned: the scan has lost those records, and the result has to say so
    rather than look like a domain that publishes none.
    """

    name = COLLECTOR_NAME

    def __init__(self, resolver: Resolver) -> None:
        self._resolver = resolver

    async def collect(self, domain: str) -> CollectionResult:
        apex = decide_apex_domain(domain)
        record_types = tuple(CHANNEL_BY_RECORD_TYPE)
        outcomes = await asyncio.gather(
            *(self._resolver.resolve(apex, record_type) for record_type in record_types),
            return_exceptions=True,
        )
        signals: list[Signal] = []
        failed_lookups: list[_FailedLookup] = []

        for record_type, outcome in zip(record_types, outcomes, strict=True):
            answer = _decide_answer(apex, record_type, outcome)
            channel = CHANNEL_BY_RECORD_TYPE[record_type]
            signals.extend(Signal(channel=channel, value=record) for record in answer.records)

            if answer.failure is not None:
                failed_lookups.append(_FailedLookup(record_type=record_type, reason=answer.failure))

        logger.debug("%s produced %d dns signals from %s", domain, len(signals), apex)
        failure = _decide_failure_or_none(tuple(failed_lookups))

        return CollectionResult(signals=tuple(signals), failure=failure)


def _decide_answer(apex: str, record_type: str, outcome: DnsAnswer | BaseException) -> DnsAnswer:
    """A resolver is contracted not to raise; one that does costs its own record type only."""
    if isinstance(outcome, DnsAnswer):
        return outcome

    if not isinstance(outcome, Exception):
        raise outcome

    logger.warning("%s %s lookup raised: %r", apex, record_type, outcome)

    return DnsAnswer(records=(), failure=FailureReasonEnum.COLLECTOR_ERROR)


def _decide_failure_or_none(failed_lookups: tuple[_FailedLookup, ...]) -> CollectionFailure | None:
    """One failure for the collector, naming every record type that was not read."""
    if len(failed_lookups) == 0:
        return None

    reason = _decide_leading_reason(failed_lookups)
    detail = "; ".join(_describe_failed_lookup(failed_lookup) for failed_lookup in failed_lookups)

    return CollectionFailure(collector=COLLECTOR_NAME, reason=reason, detail=detail)


def _decide_leading_reason(failed_lookups: tuple[_FailedLookup, ...]) -> FailureReasonEnum:
    """A timeout is the reason a reader can act on, so it speaks for a mixed set."""
    reasons = frozenset(failed_lookup.reason for failed_lookup in failed_lookups)

    if FailureReasonEnum.TIMEOUT in reasons:
        return FailureReasonEnum.TIMEOUT

    return failed_lookups[0].reason


def _describe_failed_lookup(failed_lookup: _FailedLookup) -> str:
    detail = _decide_failure_detail(failed_lookup.reason)

    return f"{failed_lookup.record_type} lookup {detail}"


def _decide_failure_detail(reason: FailureReasonEnum) -> str:
    known = DETAIL_BY_FAILURE_REASON.get(reason)

    if known is None:
        return DEFAULT_FAILURE_DETAIL

    return known
