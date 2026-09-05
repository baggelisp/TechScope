"""Deciding whether a response is the homepage or a refusal wearing its clothes.

A block is classified rather than discarded: the headers that arrived with it are real evidence,
and a Cloudflare challenge is itself proof of Cloudflare.
"""

from techscope.domain.enums import BlockReasonEnum

BLOCK_REASON_BY_STATUS: dict[int, BlockReasonEnum] = {
    403: BlockReasonEnum.FORBIDDEN,
    429: BlockReasonEnum.RATE_LIMITED,
    503: BlockReasonEnum.SERVICE_UNAVAILABLE,
}

# A real interstitial is a stub page. Imperva in particular injects `_Incapsula_Resource`
# into ordinary full-size responses too, so size is what separates a block from a page that
# merely sits behind the same vendor.
CHALLENGE_PAGE_MAXIMUM_BYTES = 50 * 1024

# Distinctive enough that an ordinary page discussing these vendors will not trip them.
CHALLENGE_MARKERS = (
    "just a moment...",
    "checking your browser before accessing",
    "cf-browser-verification",
    "attention required! | cloudflare",
    "_incapsula_resource",
    "px-captcha",
    "enable javascript and cookies to continue",
)


def decide_block_reason_or_none(status_code: int, body: str) -> BlockReasonEnum | None:
    """Resolve why this response is not a usable homepage, or ``None`` if it is one."""
    if _has_challenge_marker(body):
        return BlockReasonEnum.CHALLENGE_PAGE

    status_reason = BLOCK_REASON_BY_STATUS.get(status_code)

    if status_reason is not None:
        return status_reason

    if len(body.strip()) == 0:
        return BlockReasonEnum.EMPTY_BODY

    return None


def _has_challenge_marker(body: str) -> bool:
    if len(body) > CHALLENGE_PAGE_MAXIMUM_BYTES:
        return False

    lowered = body.lower()

    return any(marker in lowered for marker in CHALLENGE_MARKERS)
