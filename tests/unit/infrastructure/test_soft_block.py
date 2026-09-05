"""Classifying a response that came back but is not the homepage we asked for."""

import pytest

from techscope.domain.enums import BlockReasonEnum
from techscope.infrastructure.http.soft_block import (
    CHALLENGE_PAGE_MAXIMUM_BYTES,
    decide_block_reason_or_none,
)

ORDINARY_BODY = "<html><head><title>Example</title></head><body>Hello</body></html>"


@pytest.mark.parametrize(
    ("status_code", "expected_reason"),
    [
        (403, BlockReasonEnum.FORBIDDEN),
        (429, BlockReasonEnum.RATE_LIMITED),
        (503, BlockReasonEnum.SERVICE_UNAVAILABLE),
    ],
    ids=["forbidden", "rate limited", "service unavailable"],
)
def test_decide_block_reason_classifies_a_blocking_status(
    status_code: int, expected_reason: BlockReasonEnum
) -> None:
    assert decide_block_reason_or_none(status_code, ORDINARY_BODY) is expected_reason


@pytest.mark.parametrize(
    "status_code", [200, 201, 301, 404, 500], ids=["ok", "created", "moved", "missing", "error"]
)
def test_decide_block_reason_leaves_an_ordinary_response_alone(status_code: int) -> None:
    assert decide_block_reason_or_none(status_code, ORDINARY_BODY) is None


@pytest.mark.parametrize(
    "body",
    [
        "<html><head><title>Just a moment...</title></head></html>",
        "<html><body>Checking your browser before accessing example.com</body></html>",
        '<div class="cf-browser-verification">',
        "<title>Attention Required! | Cloudflare</title>",
        "<script src='/_Incapsula_Resource?SWJIYLWA=719d34d31c8e3a6e6fffd425f7e032f3'>",
        "<div id='px-captcha'>",
        "Enable JavaScript and cookies to continue",
    ],
    ids=[
        "cloudflare interstitial",
        "browser check",
        "cloudflare verification markup",
        "cloudflare attention page",
        "imperva incapsula",
        "perimeterx captcha",
        "javascript wall",
    ],
)
def test_decide_block_reason_recognises_a_challenge_page(body: str) -> None:
    assert decide_block_reason_or_none(200, body) is BlockReasonEnum.CHALLENGE_PAGE


def test_decide_block_reason_prefers_the_challenge_over_the_status() -> None:
    body = "<html><head><title>Just a moment...</title></head></html>"

    assert decide_block_reason_or_none(403, body) is BlockReasonEnum.CHALLENGE_PAGE


def test_decide_block_reason_recognises_an_empty_body() -> None:
    assert decide_block_reason_or_none(200, "") is BlockReasonEnum.EMPTY_BODY


def test_decide_block_reason_treats_whitespace_only_as_empty() -> None:
    assert decide_block_reason_or_none(200, "   \n\t  ") is BlockReasonEnum.EMPTY_BODY


def test_decide_block_reason_matches_a_challenge_marker_case_insensitively() -> None:
    body = "<TITLE>JUST A MOMENT...</TITLE>"

    assert decide_block_reason_or_none(200, body) is BlockReasonEnum.CHALLENGE_PAGE


def test_decide_block_reason_does_not_flag_a_page_that_merely_mentions_cloudflare() -> None:
    body = "<p>We are hiring engineers with Cloudflare experience.</p>"

    assert decide_block_reason_or_none(200, body) is None


def test_decide_block_reason_ignores_a_vendor_marker_inside_a_full_size_page() -> None:
    """Imperva injects its resource script into ordinary responses, not only into challenges."""
    filler = "<p>ordinary content</p>" * 5000
    body = f"{filler}<script src='/_Incapsula_Resource?SWJIYLWA=719d34d3'></script>"

    assert len(body) > CHALLENGE_PAGE_MAXIMUM_BYTES
    assert decide_block_reason_or_none(200, body) is None


def test_decide_block_reason_still_flags_a_marker_on_a_stub_page() -> None:
    body = "<html><head><title>Just a moment...</title></head></html>"

    assert len(body) < CHALLENGE_PAGE_MAXIMUM_BYTES
    assert decide_block_reason_or_none(200, body) is BlockReasonEnum.CHALLENGE_PAGE
