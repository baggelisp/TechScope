"""One polite, bounded, non-crashing homepage fetch. No test here touches the network."""

import asyncio

import httpx
import pytest
import respx

from techscope.domain.enums import BlockReasonEnum, FailureReasonEnum
from techscope.infrastructure.http.homepage_fetcher import (
    MAXIMUM_BODY_BYTES,
    TOTAL_TIMEOUT_SECONDS,
    USER_AGENT,
    HomepageFetcher,
    build_client,
)
from techscope.infrastructure.http.models import FetchFailure, FetchResult

DOMAIN = "example.com"
HTTPS_URL = "https://example.com/"
HTTP_URL = "http://example.com/"
ORDINARY_BODY = "<html><body>Hello</body></html>"


async def fetch(
    domain: str = DOMAIN, total_timeout_seconds: float = TOTAL_TIMEOUT_SECONDS
) -> FetchResult | FetchFailure:
    """Uses the production client configuration, so the tests exercise the real policy."""
    async with build_client() as client:
        fetcher = HomepageFetcher(
            client=client,
            retry_backoff_seconds=0.0,
            total_timeout_seconds=total_timeout_seconds,
        )

        return await fetcher.fetch(domain)


def expect_result(outcome: FetchResult | FetchFailure) -> FetchResult:
    assert isinstance(outcome, FetchResult)

    return outcome


def expect_failure(outcome: FetchResult | FetchFailure) -> FetchFailure:
    assert isinstance(outcome, FetchFailure)

    return outcome


@respx.mock
async def test_fetch_returns_the_body_of_a_plain_response() -> None:
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=ORDINARY_BODY))

    result = expect_result(await fetch())

    assert result.status_code == 200
    assert result.body == ORDINARY_BODY


@respx.mock
async def test_fetch_lowercases_header_names() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(200, text=ORDINARY_BODY, headers={"CF-RAY": "8abc-DFW"})
    )

    result = expect_result(await fetch())

    assert ("cf-ray", "8abc-DFW") in result.headers


@respx.mock
async def test_fetch_keeps_every_repeated_set_cookie_header() -> None:
    response = httpx.Response(
        200,
        text=ORDINARY_BODY,
        headers=[("set-cookie", "intercom-session-a=1"), ("set-cookie", "other=2")],
    )
    respx.get(HTTPS_URL).mock(return_value=response)

    result = expect_result(await fetch())
    cookie_headers = [value for name, value in result.headers if name == "set-cookie"]

    assert cookie_headers == ["intercom-session-a=1", "other=2"]


@respx.mock
async def test_fetch_identifies_itself_honestly() -> None:
    route = respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=ORDINARY_BODY))

    await fetch()

    assert route.calls.last.request.headers["user-agent"] == USER_AGENT


@respx.mock
async def test_fetch_follows_a_redirect_and_reports_the_final_url() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(301, headers={"location": "https://www.example.com/home"})
    )
    respx.get("https://www.example.com/home").mock(
        return_value=httpx.Response(200, text=ORDINARY_BODY)
    )

    result = expect_result(await fetch())

    assert result.final_url == "https://www.example.com/home"


@respx.mock
async def test_fetch_gives_up_after_too_many_redirects() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(302, headers={"location": "https://example.com/a"})
    )
    for step in range(8):
        next_url = f"https://example.com/a{'a' * (step + 1)}"
        respx.get(f"https://example.com/a{'a' * step}").mock(
            return_value=httpx.Response(302, headers={"location": next_url})
        )

    failure = expect_failure(await fetch())

    assert failure.reason is FailureReasonEnum.TOO_MANY_REDIRECTS


@respx.mock
async def test_fetch_falls_back_to_http_when_https_cannot_connect() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.ConnectError("no route"))
    respx.get(HTTP_URL).mock(return_value=httpx.Response(200, text=ORDINARY_BODY))

    result = expect_result(await fetch())

    assert result.final_url == HTTP_URL


@respx.mock
async def test_fetch_reports_a_connection_failure_when_neither_scheme_connects() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.ConnectError("no route"))
    respx.get(HTTP_URL).mock(side_effect=httpx.ConnectError("no route"))

    failure = expect_failure(await fetch())

    assert failure.reason is FailureReasonEnum.CONNECTION_FAILED


@respx.mock
async def test_fetch_retries_once_after_a_read_timeout() -> None:
    route = respx.get(HTTPS_URL).mock(
        side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, text=ORDINARY_BODY)]
    )

    result = expect_result(await fetch())

    assert result.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_fetch_reports_a_timeout_when_the_retry_also_times_out() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.ReadTimeout("slow"))

    failure = expect_failure(await fetch())

    assert failure.reason is FailureReasonEnum.TIMEOUT


@respx.mock
async def test_fetch_does_not_fall_back_to_http_after_a_read_timeout() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    http_route = respx.get(HTTP_URL).mock(return_value=httpx.Response(200, text=ORDINARY_BODY))

    await fetch()

    assert http_route.call_count == 0


@respx.mock
async def test_fetch_does_not_retry_a_client_error() -> None:
    route = respx.get(HTTPS_URL).mock(return_value=httpx.Response(404, text="missing"))

    await fetch()

    assert route.call_count == 1


@pytest.mark.parametrize(
    ("status_code", "expected_reason"),
    [
        (403, BlockReasonEnum.FORBIDDEN),
        (429, BlockReasonEnum.RATE_LIMITED),
        (503, BlockReasonEnum.SERVICE_UNAVAILABLE),
    ],
    ids=["forbidden", "rate limited", "service unavailable"],
)
@respx.mock
async def test_fetch_marks_a_soft_block_but_still_returns_the_response(
    status_code: int, expected_reason: BlockReasonEnum
) -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(status_code, text="denied", headers={"cf-ray": "8abc-DFW"})
    )

    result = expect_result(await fetch())

    assert result.block_reason is expected_reason
    assert ("cf-ray", "8abc-DFW") in result.headers


@respx.mock
async def test_fetch_marks_a_challenge_page_served_with_a_success_status() -> None:
    body = "<html><head><title>Just a moment...</title></head></html>"
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=body))

    result = expect_result(await fetch())

    assert result.block_reason is BlockReasonEnum.CHALLENGE_PAGE


@respx.mock
async def test_fetch_caps_an_oversized_body() -> None:
    oversized = "a" * (MAXIMUM_BODY_BYTES * 2)
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=oversized))

    result = expect_result(await fetch())

    assert len(result.body) == MAXIMUM_BODY_BYTES


@respx.mock
async def test_fetch_decodes_a_declared_charset() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            content="<p>café</p>".encode("latin-1"),
            headers={"content-type": "text/html; charset=latin-1"},
        )
    )

    result = expect_result(await fetch())

    assert "café" in result.body


@respx.mock
async def test_fetch_replaces_undecodable_bytes_rather_than_failing() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200, content=b"<p>\xff\xfe broken</p>", headers={"content-type": "text/html"}
        )
    )

    result = expect_result(await fetch())

    assert "broken" in result.body


@respx.mock
async def test_fetch_survives_a_charset_that_does_not_exist() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            content=b"<p>hello</p>",
            headers={"content-type": "text/html; charset=nonsense-9"},
        )
    )

    result = expect_result(await fetch())

    assert "hello" in result.body


@respx.mock
async def test_fetch_returns_a_response_that_is_not_html() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200, content=b'{"ok":true}', headers={"content-type": "application/json"}
        )
    )

    result = expect_result(await fetch())

    assert result.body == '{"ok":true}'


@respx.mock
async def test_fetch_reports_an_unexpected_protocol_error() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.RemoteProtocolError("bad framing"))

    failure = expect_failure(await fetch())

    assert failure.reason is FailureReasonEnum.INVALID_RESPONSE


@respx.mock
async def test_fetch_stops_at_the_total_budget_however_slowly_the_host_answers() -> None:
    """The outer deadline, not the per-request timeout, is what bounds a drip-feeding host."""

    async def never_finish(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5.0)

        return httpx.Response(200, text=ORDINARY_BODY)

    respx.get(HTTPS_URL).mock(side_effect=never_finish)

    failure = expect_failure(await fetch(total_timeout_seconds=0.05))

    assert failure.reason is FailureReasonEnum.TIMEOUT


@respx.mock
async def test_fetch_reports_a_host_that_cannot_be_resolved() -> None:
    """The target guard catches a host that resolves to nothing before a request is built."""
    failure = expect_failure(await fetch("no-such-host.invalid"))

    assert failure.reason is FailureReasonEnum.DNS_UNRESOLVED


@respx.mock
async def test_fetch_reports_a_host_that_is_not_a_name_at_all() -> None:
    """An emoji is refused as a name rather than sent to a resolver to puzzle over."""
    failure = expect_failure(await fetch("\U0001f600.com"))

    assert failure.reason is FailureReasonEnum.INVALID_HOST


@respx.mock
async def test_fetch_makes_at_most_two_attempts_per_scheme() -> None:
    """One retry each, then the http fallback: four connections to a dead host, never more."""
    https_route = respx.get(HTTPS_URL).mock(side_effect=httpx.ConnectError("no route"))
    http_route = respx.get(HTTP_URL).mock(side_effect=httpx.ConnectError("no route"))

    await fetch()

    assert https_route.call_count == 2
    assert http_route.call_count == 2
