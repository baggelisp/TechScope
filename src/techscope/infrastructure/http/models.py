"""What one homepage fetch produced. Private to the HTTP adapter."""

from dataclasses import dataclass

from techscope.domain.enums import BlockReasonEnum, FailureReasonEnum


@dataclass(frozen=True, slots=True)
class FetchResult:
    """A response that arrived, whether or not it was the homepage we asked for.

    ``block_reason`` is set when the host refused in a way that still told us something:
    the headers are kept either way, because a Cloudflare challenge proves Cloudflare.
    Headers are name/value pairs rather than a mapping so that repeated names — every
    ``Set-Cookie`` — survive, and their names are lowercased: the cookie extractor looks for
    ``set-cookie`` exactly.
    """

    final_url: str
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: str
    block_reason: BlockReasonEnum | None


@dataclass(frozen=True, slots=True)
class FetchFailure:
    """No response arrived at all."""

    reason: FailureReasonEnum
    detail: str


@dataclass(frozen=True, slots=True)
class RedirectTarget:
    """Where a response said to go next. A hop, not a result and not a failure."""

    location: str
