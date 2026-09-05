"""Meta tags, keyed by their name or property."""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse


def extract_meta_signals(response: ObservedResponse) -> tuple[Signal, ...]:
    return tuple(
        Signal(channel=ChannelEnum.META, value=tag.content, key=tag.name)
        for tag in response.document.meta_tags
    )
