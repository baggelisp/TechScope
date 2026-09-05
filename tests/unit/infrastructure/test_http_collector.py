"""The HTTP collector end to end, over recorded pages. No test here touches the network."""

from pathlib import Path

import httpx
import pytest
import respx

from techscope.application.ports.signal_collector import CollectionResult
from techscope.domain.enums import BlockReasonEnum, ChannelEnum, FailureReasonEnum
from techscope.domain.matcher import build_fingerprint_index, match_signals
from techscope.infrastructure.collectors.http_collector import HttpSignalCollector
from techscope.infrastructure.http.homepage_fetcher import (
    TOTAL_TIMEOUT_SECONDS,
    HomepageFetcher,
    build_client,
)
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)

DOMAIN = "example.com"
HTTPS_URL = "https://example.com/"
PAGES_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "pages"


def read_page(name: str) -> str:
    return (PAGES_DIRECTORY / name).read_text(encoding="utf-8")


async def collect(domain: str = DOMAIN) -> CollectionResult:
    async with build_client() as client:
        fetcher = HomepageFetcher(
            client=client,
            retry_backoff_seconds=0.0,
            total_timeout_seconds=TOTAL_TIMEOUT_SECONDS,
        )

        return await HttpSignalCollector(fetcher=fetcher).collect(domain)


def detect(result: CollectionResult) -> list[str]:
    fingerprints = JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()
    detections = match_signals(result.signals, build_fingerprint_index(fingerprints))

    return [detection.name for detection in detections]


@respx.mock
async def test_collector_emits_signals_from_every_response_channel() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            text=read_page("hubspot_marketing.html"),
            headers=[("cf-ray", "8abc-DFW"), ("set-cookie", "session=1; Path=/")],
        )
    )

    channels = {signal.channel for signal in (await collect()).signals}

    assert channels == {
        ChannelEnum.HEADER,
        ChannelEnum.COOKIE,
        ChannelEnum.SCRIPT_SRC,
        ChannelEnum.SCRIPT_INLINE,
        ChannelEnum.HTML,
    }


@pytest.mark.parametrize(
    ("page", "expected_technologies"),
    [
        ("shopify_storefront.html", ["Shopify"]),
        ("wordpress_blog.html", ["WordPress"]),
        ("hubspot_marketing.html", ["Google Analytics 4", "HubSpot"]),
    ],
    ids=["a Shopify storefront", "a WordPress blog", "a HubSpot marketing page"],
)
@respx.mock
async def test_collector_detects_the_technologies_a_recorded_page_uses(
    page: str, expected_technologies: list[str]
) -> None:
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=read_page(page)))

    assert detect(await collect()) == expected_technologies


@respx.mock
async def test_collector_detects_cloudflare_from_headers_alone() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200, text="<html><body>plain</body></html>", headers={"cf-ray": "8abc-DFW"}
        )
    )

    assert detect(await collect()) == ["Cloudflare"]


@respx.mock
async def test_collector_still_detects_cloudflare_behind_its_own_challenge() -> None:
    """A block is evidence: the challenge page proves the thing that served it."""
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            403,
            text=read_page("cloudflare_challenge.html"),
            headers={"cf-ray": "8abc-DFW", "cf-cache-status": "DYNAMIC"},
        )
    )

    result = await collect()

    assert detect(result) == ["Cloudflare"]
    assert result.failure is not None
    assert result.failure.reason is BlockReasonEnum.CHALLENGE_PAGE


@respx.mock
async def test_collector_detects_intercom_from_its_cookie_name() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>plain</body></html>",
            headers={"set-cookie": "intercom-session-abc=opaque; Path=/"},
        )
    )

    assert detect(await collect()) == ["Intercom"]


@respx.mock
async def test_collector_reports_a_failure_and_no_signals_when_the_fetch_fails() -> None:
    respx.get(HTTPS_URL).mock(side_effect=httpx.ConnectError("no route"))
    respx.get("http://example.com/").mock(side_effect=httpx.ConnectError("no route"))

    result = await collect()

    assert result.signals == ()
    assert result.failure is not None
    assert result.failure.reason is FailureReasonEnum.CONNECTION_FAILED


@respx.mock
async def test_collector_reports_no_failure_for_an_ordinary_page() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(200, text="<html><body>plain</body></html>")
    )

    assert (await collect()).failure is None


@respx.mock
async def test_collector_names_itself_on_a_failure() -> None:
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(429, text="slow down"))

    result = await collect()

    assert result.failure is not None
    assert result.failure.collector == "http"


@respx.mock
async def test_collector_does_not_detect_a_vendor_named_only_in_page_data() -> None:
    """The false positive this feature was almost shipped with.

    sentry.io serialises its own onboarding docs into a script element, including a code sample
    containing the Sentry CDN URL. A vendor URL in editorial text is not evidence of a load.
    """
    page = (
        "<html><body>"
        '<script type="application/json">'
        '{"snippet":"Grab the SDK: <script src=\\"https://browser.sentry-cdn.com/x/bundle.js\\">",'
        '"also":"we load cdn.segment.com/analytics.js and static.zdassets.com"}'
        "</script>"
        "</body></html>"
    )
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=page))

    assert detect(await collect()) == []


@respx.mock
async def test_collector_detects_a_vendor_that_is_really_loaded() -> None:
    """The corresponding positive: the same URL as an actual script source."""
    page = '<html><body><script src="https://browser.sentry-cdn.com/7/bundle.min.js"></script></body></html>'
    respx.get(HTTPS_URL).mock(return_value=httpx.Response(200, text=page))

    assert detect(await collect()) == ["Sentry"]
