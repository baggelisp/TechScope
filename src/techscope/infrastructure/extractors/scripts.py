"""Script sources and inline script bodies, from the one parse of the document.

Sources are kept exactly as written — protocol-relative and relative URLs are not resolved —
because that is the text upstream fingerprints are written against.
"""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse


def extract_script_signals(response: ObservedResponse) -> tuple[Signal, ...]:
    """Two channels from one tag: where a script came from, and what it says."""
    sources = [
        Signal(channel=ChannelEnum.SCRIPT_SRC, value=source)
        for source in response.document.script_sources
    ]
    inline = [
        Signal(channel=ChannelEnum.SCRIPT_INLINE, value=body)
        for body in response.document.inline_scripts
    ]

    return tuple(sources + inline)
