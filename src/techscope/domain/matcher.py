"""The matching core. Pure: no I/O, no clock, no globals.

This feature builds the per-channel index; ``match_signals`` arrives with backlog item 3.
"""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Fingerprint, FingerprintIndex, IndexedPattern


def build_fingerprint_index(fingerprints: tuple[Fingerprint, ...]) -> FingerprintIndex:
    """Group every pattern by its channel so a signal only ever meets relevant patterns."""
    patterns_by_channel: dict[ChannelEnum, list[IndexedPattern]] = {}
    fingerprint_by_name: dict[str, Fingerprint] = {}

    for fingerprint in fingerprints:
        fingerprint_by_name[fingerprint.name] = fingerprint

        for pattern in fingerprint.patterns:
            entry = IndexedPattern(technology=fingerprint.name, pattern=pattern)
            patterns_by_channel.setdefault(pattern.channel, []).append(entry)

    return FingerprintIndex(
        patterns_by_channel={
            channel: tuple(entries) for channel, entries in patterns_by_channel.items()
        },
        fingerprint_by_name=fingerprint_by_name,
    )
