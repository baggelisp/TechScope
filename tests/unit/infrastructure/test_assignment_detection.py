"""Every assignment fingerprint must detect its own signal and reject a near miss.

This is the loader and the matcher working together over the shipped database, which is what
the assignment actually grades. The near misses are the confusable cases a careless regex would
accept: a wrong TLD, a neighbouring path, a header name that merely contains the right one.
"""

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.domain.matcher import build_fingerprint_index, match_signals
from techscope.domain.models import Pattern, Signal
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)

# (technology, channel, key, matching value, near-miss value)
DETECTION_CASES = [
    (
        "HubSpot",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://js.hs-scripts.com/8912345.js",
        "https://js.hs-scripts.net/8912345.js",
    ),
    (
        "HubSpot",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://js.hsforms.net/forms/v2.js",
        "https://js.hsforms.com/forms/v2.js",
    ),
    (
        "HubSpot",
        ChannelEnum.DNS_TXT,
        None,
        "hubspot-developer-verification=abc123",
        "hubspot-verification=abc123",
    ),
    (
        "Stripe",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://js.stripe.com/v3/",
        "https://js.stripe.com/v2/",
    ),
    ("Stripe", ChannelEnum.HEADER, "x-stripe-account", "acct_1A2B", None),
    (
        "Google Analytics 4",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://www.google-analytics.com/g/collect?v=2",
        "https://www.google-analytics.com/j/collect?v=1",
    ),
    (
        "Google Analytics 4",
        ChannelEnum.SCRIPT_INLINE,
        None,
        "window.dataLayer=[];function gtag(){dataLayer.push(arguments);}",
        'var gtagId = "G-XYZ";',
    ),
    (
        "Intercom",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://widget.intercom.io/widget/abc123",
        "https://widget.intercom.com/widget/abc123",
    ),
    ("Intercom", ChannelEnum.COOKIE, "intercom-session-abc", "opaque", None),
    ("Cloudflare", ChannelEnum.HEADER, "cf-ray", "8abc1234-DFW", None),
    ("Cloudflare", ChannelEnum.HEADER, "cf-cache-status", "HIT", None),
    (
        "WordPress",
        ChannelEnum.HTML,
        None,
        '<link href="/wp-content/themes/site.css">',
        '<link href="/content/themes/site.css">',
    ),
    (
        "WordPress",
        ChannelEnum.HTML,
        None,
        '<script src="/wp-includes/js/jquery.js">',
        '<script src="/includes/js/jquery.js">',
    ),
    (
        "Shopify",
        ChannelEnum.HTML,
        None,
        '<img src="https://cdn.shopify.com/s/files/1/logo.png">',
        '<img src="https://cdn.shopifycdn.net/s/files/1/logo.png">',
    ),
    ("Shopify", ChannelEnum.HEADER, "x-shopid", "12345678", None),
    (
        "SendGrid",
        ChannelEnum.DNS_TXT,
        None,
        "v=spf1 include:sendgrid.net ~all",
        "v=spf1 include:sendgrid.com ~all",
    ),
    (
        "Salesforce",
        ChannelEnum.DNS_CNAME,
        None,
        "example.my.salesforce.com",
        "example.mysalesforce.com",
    ),
    ("Google Workspace", ChannelEnum.DNS_MX, None, "aspmx.l.google.com", "aspmx.l.googlemail.co"),
    (
        "Microsoft 365",
        ChannelEnum.DNS_MX,
        None,
        "example-com.mail.protection.outlook.com",
        "example-com.mail.protection.office.com",
    ),
    (
        "Zendesk",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://static.zdassets.com/ekr/snippet.js",
        "https://staticzdassets.com/ekr/snippet.js",
    ),
    (
        "Drift",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://js.driftt.com/include/abc/xyz.js",
        "https://js.drift.com/include/abc/xyz.js",
    ),
    (
        "Segment",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://cdn.segment.com/analytics.js/v1/abc/analytics.min.js",
        "https://cdn.segment.io/analytics.js/v1/abc/analytics.min.js",
    ),
    (
        "Sentry",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://browser.sentry-cdn.com/7.0.0/bundle.min.js",
        "https://browser.sentry-cdn.net/7.0.0/bundle.min.js",
    ),
    (
        "Hotjar",
        ChannelEnum.SCRIPT_SRC,
        None,
        "https://static.hotjar.com/c/hotjar-1234.js",
        "https://static.hotjar.io/c/hotjar-1234.js",
    ),
]


def decide_case_label(key: str | None, value: str) -> str:
    if key is not None:
        return key

    return value[:44]


# A near miss on a keyed pattern is a wrong name rather than a wrong value: the assignment's
# header and cookie patterns accept any value.
KEYED_NEAR_MISS_KEYS = {
    "x-stripe-account": "my-x-stripe-account",
    "intercom-session-abc": "my-intercom-session",
    "cf-ray": "x-cf-ray-original",
    "cf-cache-status": "x-cache-status",
    "x-shopid": "x-shop-identifier",
}

CASE_IDS = [
    f"{technology} via {channel}: {decide_case_label(key, value)}"
    for technology, channel, key, value, _ in DETECTION_CASES
]


def detect(signal: Signal) -> list[str]:
    fingerprints = JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()
    detections = match_signals((signal,), build_fingerprint_index(fingerprints))

    return [detection.name for detection in detections]


@pytest.mark.parametrize(
    ("technology", "channel", "key", "value"),
    [(technology, channel, key, value) for technology, channel, key, value, _ in DETECTION_CASES],
    ids=CASE_IDS,
)
def test_assignment_fingerprint_detects_its_own_signal(
    technology: str, channel: ChannelEnum, key: str | None, value: str
) -> None:
    assert technology in detect(Signal(channel=channel, value=value, key=key))


@pytest.mark.parametrize(
    ("technology", "channel", "key", "value", "near_miss_value"),
    DETECTION_CASES,
    ids=CASE_IDS,
)
def test_assignment_fingerprint_rejects_a_near_miss(
    technology: str, channel: ChannelEnum, key: str | None, value: str, near_miss_value: str | None
) -> None:
    near_miss = _build_near_miss(channel, key, value, near_miss_value)

    assert technology not in detect(near_miss)


def _build_near_miss(
    channel: ChannelEnum, key: str | None, value: str, near_miss_value: str | None
) -> Signal:
    if key is not None:
        return Signal(channel=channel, value=value, key=KEYED_NEAR_MISS_KEYS[key])

    if near_miss_value is None:
        raise AssertionError("a keyless case must supply a near-miss value")

    return Signal(channel=channel, value=near_miss_value, key=None)


def test_every_shipped_pattern_is_exercised_by_a_detection_case() -> None:
    """A new pattern with no case of its own fails here, rather than shipping untested."""
    fingerprints = JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()
    unexercised = [
        f"{fingerprint.name}: {pattern.decide_source_text()}"
        for fingerprint in fingerprints
        for pattern in fingerprint.patterns
        if not _is_pattern_exercised(fingerprint.name, pattern)
    ]

    assert unexercised == []


def _is_pattern_exercised(technology: str, pattern: Pattern) -> bool:
    for case_technology, channel, key, value, _ in DETECTION_CASES:
        if case_technology != technology or channel is not pattern.channel:
            continue

        if _does_pattern_accept(pattern, key, value):
            return True

    return False


def _does_pattern_accept(pattern: Pattern, key: str | None, value: str) -> bool:
    if not _does_key_accept(pattern, key):
        return False

    return pattern.value_regex.search(value) is not None


def _does_key_accept(pattern: Pattern, key: str | None) -> bool:
    if pattern.key_regex is None:
        return True

    if key is None:
        return False

    return pattern.key_regex.fullmatch(key) is not None


def test_a_page_with_several_signals_reports_every_technology() -> None:
    fingerprints = JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()
    signals = (
        Signal(channel=ChannelEnum.HEADER, value="8abc1234-DFW", key="cf-ray"),
        Signal(channel=ChannelEnum.SCRIPT_SRC, value="https://js.stripe.com/v3/"),
        Signal(channel=ChannelEnum.HTML, value='<link href="/wp-content/style.css">'),
    )

    detections = match_signals(signals, build_fingerprint_index(fingerprints))

    assert [detection.name for detection in detections] == ["Cloudflare", "Stripe", "WordPress"]
