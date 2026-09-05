"""The raw response body, as one signal.

Several upstream fingerprints match markup that belongs to no single tag — a path inside an
attribute, a comment a platform leaves behind — so the whole body stays available.
"""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse


def extract_html_signal(response: ObservedResponse) -> tuple[Signal, ...]:
    body = response.result.body

    if len(body) == 0:
        return ()

    return (Signal(channel=ChannelEnum.HTML, value=body),)
