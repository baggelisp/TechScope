"""The five response extractors. Each turns one part of a response into signals."""

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.cookies import extract_cookie_signals
from techscope.infrastructure.extractors.headers import extract_header_signals
from techscope.infrastructure.extractors.html import extract_html_signal
from techscope.infrastructure.extractors.meta import extract_meta_signals
from techscope.infrastructure.extractors.observed_response import (
    ObservedResponse,
    build_observed_response,
)
from techscope.infrastructure.extractors.registry import EXTRACTORS, Extractor
from techscope.infrastructure.extractors.scripts import extract_script_signals
from techscope.infrastructure.http.models import FetchResult


def build_response(body: str = "", headers: tuple[tuple[str, str], ...] = ()) -> ObservedResponse:
    result = FetchResult(
        final_url="https://example.com/",
        status_code=200,
        headers=headers,
        body=body,
        block_reason=None,
    )

    return build_observed_response(result)


def list_values(signals: tuple[Signal, ...]) -> list[str]:
    return [signal.value for signal in signals]


def list_keys(signals: tuple[Signal, ...]) -> list[str | None]:
    return [signal.key for signal in signals]


def test_headers_extractor_emits_one_signal_per_header() -> None:
    response = build_response(headers=(("cf-ray", "8abc-DFW"), ("server", "cloudflare")))

    signals = extract_header_signals(response)

    assert list_keys(signals) == ["cf-ray", "server"]
    assert list_values(signals) == ["8abc-DFW", "cloudflare"]


def test_headers_extractor_uses_the_header_channel() -> None:
    response = build_response(headers=(("cf-ray", "8abc-DFW"),))

    assert extract_header_signals(response)[0].channel is ChannelEnum.HEADER


def test_headers_extractor_keeps_every_repeated_header() -> None:
    response = build_response(headers=(("set-cookie", "a=1"), ("set-cookie", "b=2")))

    assert list_values(extract_header_signals(response)) == ["a=1", "b=2"]


def test_headers_extractor_of_a_response_without_headers_emits_nothing() -> None:
    assert extract_header_signals(build_response()) == ()


def test_cookies_extractor_reads_the_name_and_value() -> None:
    response = build_response(headers=(("set-cookie", "intercom-session-x=abc; Path=/"),))

    signals = extract_cookie_signals(response)

    assert list_keys(signals) == ["intercom-session-x"]
    assert list_values(signals) == ["abc"]


def test_cookies_extractor_uses_the_cookie_channel() -> None:
    response = build_response(headers=(("set-cookie", "a=1"),))

    assert extract_cookie_signals(response)[0].channel is ChannelEnum.COOKIE


def test_cookies_extractor_reads_every_set_cookie_header() -> None:
    response = build_response(
        headers=(("set-cookie", "first=1; Secure"), ("set-cookie", "second=2; HttpOnly"))
    )

    assert list_keys(extract_cookie_signals(response)) == ["first", "second"]


def test_cookies_extractor_ignores_other_headers() -> None:
    response = build_response(headers=(("server", "nginx=1"),))

    assert extract_cookie_signals(response) == ()


@pytest.mark.parametrize(
    "header_value",
    ["novalue", "; Path=/", "=orphaned", "   "],
    ids=["no separator", "no name or value", "empty name", "whitespace only"],
)
def test_cookies_extractor_skips_a_malformed_cookie(header_value: str) -> None:
    response = build_response(headers=(("set-cookie", header_value),))

    assert extract_cookie_signals(response) == ()


def test_cookies_extractor_keeps_an_equals_sign_inside_the_value() -> None:
    response = build_response(headers=(("set-cookie", "token=abc=def==; Path=/"),))

    assert list_values(extract_cookie_signals(response)) == ["abc=def=="]


def test_cookies_extractor_accepts_a_cookie_with_an_empty_value() -> None:
    response = build_response(headers=(("set-cookie", "flag=; Path=/"),))

    signals = extract_cookie_signals(response)

    assert list_keys(signals) == ["flag"]
    assert list_values(signals) == [""]


def test_scripts_extractor_emits_sources_and_inline_bodies() -> None:
    body = '<script src="https://js.stripe.com/v3/"></script><script>gtag("js");</script>'

    signals = extract_script_signals_for(body)

    assert [(signal.channel, signal.value) for signal in signals] == [
        (ChannelEnum.SCRIPT_SRC, "https://js.stripe.com/v3/"),
        (ChannelEnum.SCRIPT_INLINE, 'gtag("js");'),
    ]


def extract_script_signals_for(body: str) -> tuple[Signal, ...]:
    return extract_script_signals(build_response(body=body))


def test_scripts_extractor_leaves_a_source_signal_unkeyed() -> None:
    signals = extract_script_signals_for('<script src="https://a.example/b.js"></script>')

    assert signals[0].key is None


def test_scripts_extractor_of_a_page_without_scripts_emits_nothing() -> None:
    assert extract_script_signals_for("<html><body>nothing here</body></html>") == ()


def test_meta_extractor_keys_by_the_meta_name() -> None:
    response = build_response(body='<meta name="generator" content="WordPress 6.4">')

    signals = extract_meta_signals(response)

    assert list_keys(signals) == ["generator"]
    assert list_values(signals) == ["WordPress 6.4"]


def test_meta_extractor_uses_the_meta_channel() -> None:
    response = build_response(body='<meta name="generator" content="WordPress">')

    assert extract_meta_signals(response)[0].channel is ChannelEnum.META


def test_meta_extractor_of_a_page_without_meta_tags_emits_nothing() -> None:
    assert extract_meta_signals(build_response(body="<p>text</p>")) == ()


def test_html_extractor_emits_the_whole_body() -> None:
    body = '<html><link href="/wp-content/style.css"></html>'

    signals = extract_html_signal(build_response(body=body))

    assert list_values(signals) == [body]
    assert signals[0].channel is ChannelEnum.HTML


def test_html_extractor_of_an_empty_body_emits_nothing() -> None:
    assert extract_html_signal(build_response(body="")) == ()


def test_registry_lists_every_extractor_once() -> None:
    assert len(EXTRACTORS) == len(set(EXTRACTORS))


def test_registry_covers_every_response_channel() -> None:
    body = '<script src="https://a.example/b.js"></script><script>run();</script>'
    body += '<meta name="generator" content="WordPress">'
    response = build_response(body=body, headers=(("set-cookie", "a=1"),))
    extractors: tuple[Extractor, ...] = EXTRACTORS
    channels = {signal.channel for extractor in extractors for signal in extractor(response)}

    assert channels == {
        ChannelEnum.HEADER,
        ChannelEnum.COOKIE,
        ChannelEnum.SCRIPT_SRC,
        ChannelEnum.SCRIPT_INLINE,
        ChannelEnum.META,
        ChannelEnum.HTML,
    }
