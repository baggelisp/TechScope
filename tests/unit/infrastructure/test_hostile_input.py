"""One test per guard, driven by the hostile inputs each guard exists to survive.

Every page this scanner reads is written by someone else. These are the shapes that turn that
into a problem: a regex that backtracks, a body that expands, a redirect that points inward, and
content that writes control codes into our own output.
"""

import time
from pathlib import Path

import httpx
import pytest
import respx

from techscope.domain.enums import ChannelEnum, FailureReasonEnum
from techscope.domain.errors import FingerprintLoadError
from techscope.domain.matcher import (
    MAXIMUM_EVIDENCE_TEXT_LENGTH,
    MAXIMUM_MATCH_INPUT_LENGTH,
    build_fingerprint_index,
    match_signals,
)
from techscope.domain.models import Signal
from techscope.infrastructure.http.homepage_fetcher import (
    MAXIMUM_BODY_BYTES,
    TOTAL_TIMEOUT_SECONDS,
    HomepageFetcher,
    build_client,
)
from techscope.infrastructure.http.models import FetchFailure, FetchResult
from techscope.infrastructure.repositories.wappalyzer_pattern import build_pattern
from tests.support.builders import build_test_fingerprint, build_test_pattern

HOSTILE_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "hostile"
HTTPS_URL = "https://example.com/"
BACKTRACKING_BUDGET_SECONDS = 0.1


def read_hostile(name: str) -> str:
    return (HOSTILE_DIRECTORY / name).read_text(encoding="utf-8")


async def fetch(domain: str = "example.com") -> FetchResult | FetchFailure:
    async with build_client() as client:
        fetcher = HomepageFetcher(
            client=client,
            retry_backoff_seconds=0.0,
            total_timeout_seconds=TOTAL_TIMEOUT_SECONDS,
        )

        return await fetcher.fetch(domain)


@pytest.mark.parametrize(
    "regex_text",
    [
        r"(a+)+$",
        r"(a*)*$",
        r"([a-z]+)*$",
        r"(\w+\s?)*$",
        r"(x+x+)+y",
        r"(a|ab)+$",
        r"(.*)*x",
        r"(a|a)+$",
        r"(?:a|a)+$",
        r"([a-z]|[a-z]{2})+$",
        r"(a+|b)+$",
        r"(a{1,}){2,}$",
        r"(?P<repeated>a+)+$",
        r"(?i:a|a)+$",
    ],
    ids=[
        "nested plus",
        "nested star",
        "quantified class",
        "all-optional body",
        "two quantified atoms",
        "overlapping branches",
        "nested any",
        "identical branches",
        "identical branches in a non-capturing group",
        "one branch a prefix of the other by element",
        "a branch that grows without bound",
        "the brace spelling of nested plus",
        "a named group hiding a nested plus",
        "identical branches behind an inline flag",
    ],
)
def test_a_catastrophic_pattern_is_refused_at_load_time(regex_text: str) -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_pattern("Hostile Tech", ChannelEnum.HTML, regex_text, None)

    assert raised.value.technology == "Hostile Tech"


def test_refusing_a_catastrophic_pattern_is_immediate() -> None:
    """The point of refusing at load time: nothing ever runs the pattern against a page."""
    started_at = time.perf_counter()

    with pytest.raises(FingerprintLoadError):
        build_pattern("Hostile Tech", ChannelEnum.HTML, r"(a+)+$", None)

    assert time.perf_counter() - started_at < BACKTRACKING_BUDGET_SECONDS


def test_the_page_that_would_have_backtracked_is_matched_quickly() -> None:
    """The same page, against the patterns that survive the guard, finishes at once."""
    page = read_hostile("backtracking_page.html")
    fingerprint = build_test_fingerprint(
        "Some Tech", (build_test_pattern(ChannelEnum.HTML, r"a{200}"),)
    )
    index = build_fingerprint_index((fingerprint,))
    signal = Signal(channel=ChannelEnum.HTML, value=page)

    started_at = time.perf_counter()
    detections = match_signals((signal,), index)

    assert time.perf_counter() - started_at < BACKTRACKING_BUDGET_SECONDS
    assert [detection.name for detection in detections] == ["Some Tech"]


@respx.mock
async def test_a_decompression_bomb_stops_at_the_body_cap() -> None:
    """Fifty megabytes arrive as fifty kilobytes; the cap counts what was decoded."""
    bomb = (HOSTILE_DIRECTORY / "gzip_bomb.html.gz").read_bytes()
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            200,
            content=bomb,
            headers={"content-encoding": "gzip", "content-type": "text/html"},
        )
    )

    result = await fetch()

    assert isinstance(result, FetchResult)
    assert len(result.body) == MAXIMUM_BODY_BYTES


@respx.mock
async def test_a_redirect_to_loopback_is_refused() -> None:
    """The reason every hop is checked and not only the first."""
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(302, headers={"location": "http://127.0.0.1:8080/admin"})
    )
    loopback = respx.get("http://127.0.0.1:8080/admin").mock(
        return_value=httpx.Response(200, text="internal")
    )

    result = await fetch()

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.PRIVATE_TARGET
    assert loopback.call_count == 0


@respx.mock
async def test_a_redirect_to_a_private_network_is_refused() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(302, headers={"location": "http://10.0.0.5/"})
    )

    result = await fetch()

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.PRIVATE_TARGET


@respx.mock
async def test_a_redirect_to_the_cloud_metadata_address_is_refused() -> None:
    """169.254.169.254 is the address a scanner is most often pointed at on purpose."""
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(
            302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
        )
    )

    result = await fetch()

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.PRIVATE_TARGET


@respx.mock
async def test_a_redirect_to_a_non_http_scheme_is_refused() -> None:
    respx.get(HTTPS_URL).mock(
        return_value=httpx.Response(302, headers={"location": "file:///etc/passwd"})
    )

    result = await fetch()

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.INVALID_HOST


@respx.mock
async def test_a_public_name_that_resolves_to_loopback_is_refused(
    dns_answers: dict[str, tuple[str, ...]],
) -> None:
    """The shape of a rebinding attack: an ordinary name, a private answer.

    No route is mocked, so if the guard let this through respx would raise instead of returning.
    """
    dns_answers["intranet.example"] = ("127.0.0.1",)

    result = await fetch("intranet.example")

    assert isinstance(result, FetchFailure)
    assert result.reason is FailureReasonEnum.PRIVATE_TARGET


def test_control_characters_never_reach_the_evidence() -> None:
    """A crafted page must not write terminal escapes or bidi overrides into our output."""
    hostile_value = "https://js.stripe.com/v3/\x00\x1b[31m‮txetdesrever‬"
    fingerprint = build_test_fingerprint(
        "Stripe", (build_test_pattern(ChannelEnum.SCRIPT_SRC, r"js\.stripe\.com/v3.*"),)
    )
    index = build_fingerprint_index((fingerprint,))
    signal = Signal(channel=ChannelEnum.SCRIPT_SRC, value=hostile_value)

    matched = match_signals((signal,), index)[0].evidence[0].matched_text

    assert "\x00" not in matched
    assert "\x1b" not in matched
    assert "‮" not in matched
    # What survives is printable text: the escape's payload is left, its ESC byte is not.
    assert matched.startswith("js.stripe.com/v3/")


def test_evidence_from_a_hostile_page_is_length_capped() -> None:
    fingerprint = build_test_fingerprint("Some Tech", (build_test_pattern(ChannelEnum.HTML, "a+"),))
    index = build_fingerprint_index((fingerprint,))
    signal = Signal(channel=ChannelEnum.HTML, value="a" * (MAXIMUM_EVIDENCE_TEXT_LENGTH * 50))

    matched = match_signals((signal,), index)[0].evidence[0].matched_text

    assert len(matched) == MAXIMUM_EVIDENCE_TEXT_LENGTH


# Every spelling of the same catastrophic shape has to be refused, because a rule that reads only
# one of them is a rule an attacker writes around rather than satisfies.
EQUIVALENT_SPELLINGS = [
    (r"(a+)+$", r"(a{1,}){2,}$"),
    (r"(a+)+$", r"(?P<repeated>a+)+$"),
    (r"(a|a)+$", r"(?:a|a)+$"),
]


@pytest.mark.parametrize(
    ("plain", "disguised"),
    EQUIVALENT_SPELLINGS,
    ids=["brace for plus", "named group for plain group", "non-capturing for plain group"],
)
def test_a_catastrophic_shape_is_refused_however_it_is_written(plain: str, disguised: str) -> None:
    with pytest.raises(FingerprintLoadError):
        build_pattern("Hostile Tech", ChannelEnum.HTML, plain, None)

    with pytest.raises(FingerprintLoadError):
        build_pattern("Hostile Tech", ChannelEnum.HTML, disguised, None)


@pytest.mark.parametrize(
    "regex_text",
    [
        r"(\.\d+)+",
        r"(?:foo|bar)+",
        r"[a-z]+\.js",
        r"js\.stripe\.com/v3",
        r"(?:www\.)?example\.com",
        r"(\d+)\.(\d+)\.(\d+)",
        r"(?:https?://)?([\w-]+\.)+com",
    ],
    ids=[
        "a literal anchors each repetition",
        "distinct alternatives",
        "a quantifier with a literal after it",
        "an ordinary script URL",
        "an optional prefix",
        "a version number",
        "a hostname",
    ],
)
def test_an_ordinary_pattern_is_not_refused(regex_text: str) -> None:
    """The rule has to stay narrow: it rejects none of the 44,980 upstream pattern texts."""
    pattern = build_pattern("Some Tech", ChannelEnum.HTML, regex_text, None)

    assert pattern.value_source == regex_text


def test_the_matcher_bounds_what_one_pattern_is_run_against() -> None:
    """The matcher does not take its caller's word that the input was capped."""
    fingerprint = build_test_fingerprint(
        "Some Tech", (build_test_pattern(ChannelEnum.HTML, r"needle"),)
    )
    index = build_fingerprint_index((fingerprint,))
    beyond_the_cap = "a" * MAXIMUM_MATCH_INPUT_LENGTH + "needle"
    signal = Signal(channel=ChannelEnum.HTML, value=beyond_the_cap)

    assert match_signals((signal,), index) == ()


def test_cleaning_the_evidence_does_not_walk_a_whole_hostile_page() -> None:
    """A greedy pattern can match most of a 2 MB page; only the quoted part may be inspected."""
    fingerprint = build_test_fingerprint(
        "Some Tech", (build_test_pattern(ChannelEnum.HTML, r"x.*"),)
    )
    index = build_fingerprint_index((fingerprint,))
    signal = Signal(channel=ChannelEnum.HTML, value="x" + "\u200b" * 2_000_000)

    started_at = time.perf_counter()
    detections = match_signals((signal,), index)

    assert time.perf_counter() - started_at < BACKTRACKING_BUDGET_SECONDS
    assert len(detections[0].evidence[0].matched_text) <= MAXIMUM_EVIDENCE_TEXT_LENGTH
