"""Every response header, as a keyed signal."""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse


def extract_header_signals(response: ObservedResponse) -> tuple[Signal, ...]:
    """One signal per header value. Repeated names each get their own signal."""
    return tuple(
        Signal(channel=ChannelEnum.HEADER, value=value, key=name)
        for name, value in response.result.headers
    )
