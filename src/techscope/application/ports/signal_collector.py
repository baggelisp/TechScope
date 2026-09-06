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
    # Where the signals were actually read from, when that is not simply the domain. Four of the
    # assignment's own domains redirect to the company that acquired them, and a detection is
    # only honest if the page it came from is on the record.
    observed_url: str | None = None


class SignalCollector(Protocol):
    """Collects signals for one domain. Never raises: a problem comes back as a failure."""

    name: str

    async def collect(self, domain: str) -> CollectionResult: ...
