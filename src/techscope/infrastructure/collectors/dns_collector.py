"""The DNS source of signals: mail, verification and alias records on the apex.

These are the signals a homepage cannot give. A mail exchanger names the mail provider, a TXT
record carries the verification tokens a vendor asks a customer to publish, and a CNAME names
whoever the domain points at.
"""

import asyncio
import logging

from techscope.application.ports.signal_collector import CollectionResult
from techscope.domain.domain_name import decide_apex_domain
from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.dns.resolver import Resolver

logger = logging.getLogger(__name__)

COLLECTOR_NAME = "dns"

# The one place a record type becomes a channel. Adding a type is an entry here.
CHANNEL_BY_RECORD_TYPE: dict[str, ChannelEnum] = {
    "MX": ChannelEnum.DNS_MX,
    "TXT": ChannelEnum.DNS_TXT,
    "CNAME": ChannelEnum.DNS_CNAME,
}


class DnsSignalCollector:
    """Queries every record type concurrently and turns the answers into signals."""

    name = COLLECTOR_NAME

    def __init__(self, resolver: Resolver) -> None:
        self._resolver = resolver

    async def collect(self, domain: str) -> CollectionResult:
        apex = decide_apex_domain(domain)
        record_types = tuple(CHANNEL_BY_RECORD_TYPE)
        answers = await asyncio.gather(
            *(self._resolver.resolve(apex, record_type) for record_type in record_types),
            return_exceptions=True,
        )
        signals: list[Signal] = []

        for record_type, records in zip(record_types, answers, strict=True):
            channel = CHANNEL_BY_RECORD_TYPE[record_type]
            signals.extend(
                Signal(channel=channel, value=record)
                for record in _decide_records(apex, record_type, records)
            )

        logger.debug("%s produced %d dns signals from %s", domain, len(signals), apex)

        return CollectionResult(signals=tuple(signals), failure=None)


def _decide_records(
    apex: str, record_type: str, answer: tuple[str, ...] | BaseException
) -> tuple[str, ...]:
    """A resolver is contracted not to raise; one that does costs its own record type only."""
    if isinstance(answer, tuple):
        return answer

    if not isinstance(answer, Exception):
        raise answer

    logger.warning("%s %s lookup raised: %r", apex, record_type, answer)

    return ()
