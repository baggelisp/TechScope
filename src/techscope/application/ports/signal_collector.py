"""The port every signal source implements, whatever it talks to."""

from dataclasses import dataclass
from typing import Protocol

from techscope.domain.models import CollectionFailure, Signal


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """What one collector gathered for one domain, and what stopped it doing more.

    Signals and a failure are not alternatives. A soft-blocked host still returns the response
    headers it sent with the block, so the result carries both.
    """

    signals: tuple[Signal, ...]
    failure: CollectionFailure | None


class SignalCollector(Protocol):
    """Collects signals for one domain. Never raises: a problem comes back as a failure."""

    name: str

    async def collect(self, domain: str) -> CollectionResult: ...
