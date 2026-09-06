"""The matching core: signals against a fingerprint index, with confidence and evidence."""

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.domain.matcher import (
    MAXIMUM_EVIDENCE_TEXT_LENGTH,
    MINIMUM_REPORTED_CONFIDENCE,
    build_fingerprint_index,
    match_signals,
)
from techscope.domain.models import Detection, Fingerprint, Signal
from tests.support.builders import (
    build_test_fingerprint,
    build_test_implication,
    build_test_pattern,
)


def match(signals: tuple[Signal, ...], *fingerprints: Fingerprint) -> tuple[Detection, ...]:
    return match_signals(signals, build_fingerprint_index(fingerprints))


def list_names(detections: tuple[Detection, ...]) -> list[str]:
    return [detection.name for detection in detections]


def build_script_signal(value: str) -> Signal:
    return Signal(channel=ChannelEnum.SCRIPT_SRC, value=value)


STRIPE = build_test_fingerprint(
    "Stripe", (build_test_pattern(ChannelEnum.SCRIPT_SRC, r"js\.stripe\.com/v3"),)
)


def test_match_signals_reports_a_technology_whose_pattern_matches() -> None:
    detections = match((build_script_signal("https://js.stripe.com/v3/"),), STRIPE)

    assert list_names(detections) == ["Stripe"]


def test_match_signals_reports_nothing_when_no_pattern_matches() -> None:
    detections = match((build_script_signal("https://js.stripe.com/v2/"),), STRIPE)

    assert detections == ()


def test_match_signals_with_no_signals_reports_nothing() -> None:
    assert match((), STRIPE) == ()


def test_match_signals_ignores_a_signal_on_a_channel_with_no_patterns() -> None:
    signal = Signal(channel=ChannelEnum.DNS_MX, value="js.stripe.com/v3")

    assert match((signal,), STRIPE) == ()


def test_match_signals_reports_a_technology_once_when_two_patterns_match() -> None:
    wordpress = build_test_fingerprint(
        "WordPress",
        (
            build_test_pattern(ChannelEnum.HTML, "/wp-content/"),
            build_test_pattern(ChannelEnum.HTML, "/wp-includes/"),
        ),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="/wp-content/ and /wp-includes/")

    detections = match((signal,), wordpress)

    assert list_names(detections) == ["WordPress"]


def test_match_signals_collects_evidence_from_every_matching_pattern() -> None:
    wordpress = build_test_fingerprint(
        "WordPress",
        (
            build_test_pattern(ChannelEnum.HTML, "/wp-content/"),
            build_test_pattern(ChannelEnum.HTML, "/wp-includes/"),
        ),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="/wp-content/ and /wp-includes/")

    detections = match((signal,), wordpress)

    assert [evidence.pattern_source for evidence in detections[0].evidence] == [
        "/wp-content/",
        "/wp-includes/",
    ]


def test_match_signals_sorts_detections_by_technology_name() -> None:
    sentry = build_test_fingerprint(
        "Sentry", (build_test_pattern(ChannelEnum.SCRIPT_SRC, "sentry-cdn"),)
    )
    drift = build_test_fingerprint("Drift", (build_test_pattern(ChannelEnum.SCRIPT_SRC, "driftt"),))
    signals = (build_script_signal("driftt and sentry-cdn"),)

    detections = match(signals, sentry, drift, STRIPE)

    assert list_names(detections) == ["Drift", "Sentry"]


def test_match_signals_takes_the_highest_confidence_among_matching_patterns() -> None:
    technology = build_test_fingerprint(
        "Some Tech",
        (
            build_test_pattern(ChannelEnum.SCRIPT_SRC, "weak-signal", confidence=60),
            build_test_pattern(ChannelEnum.SCRIPT_SRC, "strong-signal", confidence=95),
        ),
    )
    signals = (build_script_signal("weak-signal and strong-signal"),)

    detections = match(signals, technology)

    assert detections[0].confidence == 95


def test_match_signals_reports_a_pattern_at_the_reporting_threshold() -> None:
    technology = build_test_fingerprint(
        "Some Tech",
        (
            build_test_pattern(
                ChannelEnum.SCRIPT_SRC, "signal", confidence=MINIMUM_REPORTED_CONFIDENCE
            ),
        ),
    )

    detections = match((build_script_signal("signal"),), technology)

    assert list_names(detections) == ["Some Tech"]


def test_match_signals_hides_a_pattern_below_the_reporting_threshold() -> None:
    technology = build_test_fingerprint(
        "Some Tech",
        (
            build_test_pattern(
                ChannelEnum.SCRIPT_SRC, "signal", confidence=MINIMUM_REPORTED_CONFIDENCE - 1
            ),
        ),
    )

    assert match((build_script_signal("signal"),), technology) == ()


def test_match_signals_matches_a_keyed_pattern_on_the_signal_key() -> None:
    cloudflare = build_test_fingerprint(
        "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="8abc-DFW", key="cf-ray")

    assert list_names(match((signal,), cloudflare)) == ["Cloudflare"]


def test_match_signals_matches_a_header_key_case_insensitively() -> None:
    cloudflare = build_test_fingerprint(
        "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="8abc-DFW", key="CF-RAY")

    assert list_names(match((signal,), cloudflare)) == ["Cloudflare"]


def test_match_signals_rejects_a_key_that_merely_contains_the_pattern() -> None:
    """Why the key is matched end to end: otherwise a literal key becomes a substring test.

    The F5 BigIP cookie key `TIN` would otherwise match the ordinary WordPress cookie
    `wp-settings-time-1`, reporting F5 BigIP on every WordPress site.
    """
    big_ip = build_test_fingerprint(
        "F5 BigIP", (build_test_pattern(ChannelEnum.COOKIE, key_source="TIN"),)
    )
    signal = Signal(channel=ChannelEnum.COOKIE, value="1", key="wp-settings-time-1")

    assert match((signal,), big_ip) == ()


def test_match_signals_rejects_a_key_that_merely_starts_with_the_pattern() -> None:
    """`core-js` declares the global `core`; a site with `window.corebine` is not using it."""
    core_js = build_test_fingerprint(
        "core-js", (build_test_pattern(ChannelEnum.JS_GLOBAL, key_source="core"),)
    )
    signal = Signal(channel=ChannelEnum.JS_GLOBAL, value="", key="corebine")

    assert match((signal,), core_js) == ()


def test_match_signals_allows_a_key_pattern_that_declares_its_own_wildcard() -> None:
    stripe_header = build_test_fingerprint(
        "Stripe", (build_test_pattern(ChannelEnum.HEADER, key_source="X-Stripe-.*"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="acct_1", key="x-stripe-account")

    assert list_names(match((signal,), stripe_header)) == ["Stripe"]


def test_match_signals_keyed_pattern_ignores_a_signal_without_a_key() -> None:
    cloudflare = build_test_fingerprint(
        "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="cf-ray")

    assert match((signal,), cloudflare) == ()


def test_match_signals_keyed_pattern_also_constrains_the_value() -> None:
    technology = build_test_fingerprint(
        "Some Tech", (build_test_pattern(ChannelEnum.HEADER, "nginx", key_source="server"),)
    )
    matching = Signal(channel=ChannelEnum.HEADER, value="nginx/1.25", key="server")
    other = Signal(channel=ChannelEnum.HEADER, value="apache/2.4", key="server")

    assert list_names(match((matching,), technology)) == ["Some Tech"]
    assert match((other,), technology) == ()


def test_match_signals_matches_a_javascript_global_by_name() -> None:
    stripe_global = build_test_fingerprint(
        "Stripe", (build_test_pattern(ChannelEnum.JS_GLOBAL, key_source="Stripe"),)
    )
    signal = Signal(channel=ChannelEnum.JS_GLOBAL, value="", key="Stripe")

    assert list_names(match((signal,), stripe_global)) == ["Stripe"]


def test_match_signals_matches_an_inline_script_body() -> None:
    analytics = build_test_fingerprint(
        "Google Analytics 4", (build_test_pattern(ChannelEnum.SCRIPT_INLINE, r"gtag\("),)
    )
    signal = Signal(channel=ChannelEnum.SCRIPT_INLINE, value="function gtag(){dataLayer.push()}")

    assert list_names(match((signal,), analytics)) == ["Google Analytics 4"]


def test_match_signals_evidence_names_the_channel_key_and_pattern() -> None:
    cloudflare = build_test_fingerprint(
        "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="8abc-DFW", key="cf-ray")

    evidence = match((signal,), cloudflare)[0].evidence[0]

    assert evidence.channel is ChannelEnum.HEADER
    assert evidence.key == "cf-ray"
    assert evidence.pattern_source == "cf-ray"


def test_match_signals_evidence_quotes_the_matched_text() -> None:
    detections = match((build_script_signal("https://js.stripe.com/v3/"),), STRIPE)

    assert detections[0].evidence[0].matched_text == "js.stripe.com/v3"


def test_match_signals_evidence_quotes_the_whole_value_when_the_pattern_accepts_any() -> None:
    cloudflare = build_test_fingerprint(
        "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
    )
    signal = Signal(channel=ChannelEnum.HEADER, value="8abc-DFW", key="cf-ray")

    assert match((signal,), cloudflare)[0].evidence[0].matched_text == "8abc-DFW"


def test_match_signals_evidence_truncates_a_very_long_match() -> None:
    technology = build_test_fingerprint("Some Tech", (build_test_pattern(ChannelEnum.HTML, "a+"),))
    signal = Signal(channel=ChannelEnum.HTML, value="a" * 5000)

    matched_text = match((signal,), technology)[0].evidence[0].matched_text

    assert len(matched_text) == MAXIMUM_EVIDENCE_TEXT_LENGTH


def test_match_signals_adds_an_implied_technology() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, r"cdn\.shopify\.com"),),
        implies=(build_test_implication("Ruby"),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="cdn.shopify.com/s/files")

    assert list_names(match((signal,), shopify)) == ["Ruby", "Shopify"]


def test_match_signals_gives_an_implied_technology_the_implier_confidence() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, r"cdn\.shopify\.com", confidence=80),),
        implies=(build_test_implication("Ruby"),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="cdn.shopify.com/s/files")

    detections = {detection.name: detection.confidence for detection in match((signal,), shopify)}

    assert detections == {"Shopify": 80, "Ruby": 80}


def test_match_signals_carries_no_evidence_for_an_implied_technology() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, r"cdn\.shopify\.com"),),
        implies=(build_test_implication("Ruby"),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="cdn.shopify.com/s/files")

    implied = [detection for detection in match((signal,), shopify) if detection.name == "Ruby"]

    assert implied[0].evidence == ()


def test_match_signals_follows_an_implies_chain() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Ruby"),),
    )
    ruby = build_test_fingerprint("Ruby", implies=(build_test_implication("Rack"),))
    rack = build_test_fingerprint("Rack")
    signal = Signal(channel=ChannelEnum.HTML, value="shopify")

    detections = match((signal,), shopify, ruby, rack)

    assert list_names(detections) == ["Rack", "Ruby", "Shopify"]


def test_match_signals_terminates_on_an_implies_cycle() -> None:
    first = build_test_fingerprint(
        "First",
        (build_test_pattern(ChannelEnum.HTML, "seen"),),
        implies=(build_test_implication("Second"),),
    )
    second = build_test_fingerprint("Second", implies=(build_test_implication("First"),))
    signal = Signal(channel=ChannelEnum.HTML, value="seen")

    detections = match((signal,), first, second)

    assert list_names(detections) == ["First", "Second"]


def test_match_signals_keeps_the_direct_evidence_of_a_technology_that_is_also_implied() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Ruby"),),
    )
    ruby = build_test_fingerprint("Ruby", (build_test_pattern(ChannelEnum.HTML, "ruby-lang"),))
    signal = Signal(channel=ChannelEnum.HTML, value="shopify and ruby-lang")

    detections = {detection.name: detection for detection in match((signal,), shopify, ruby)}

    assert detections["Ruby"].evidence != ()


def test_match_signals_reports_an_implied_technology_that_is_not_in_the_database() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Unknown Thing"),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="shopify")

    assert "Unknown Thing" in list_names(match((signal,), shopify))


def test_match_signals_does_not_let_an_unreported_technology_imply_another() -> None:
    """Implies is resolved after the confidence threshold, so a weak match implies nothing."""
    weak = build_test_fingerprint(
        "Weak Tech",
        (build_test_pattern(ChannelEnum.HTML, "seen", confidence=MINIMUM_REPORTED_CONFIDENCE - 1),),
        implies=(build_test_implication("Implied Tech"),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="seen")

    assert match((signal,), weak) == ()


def test_match_signals_raises_an_implied_confidence_when_a_stronger_implier_appears() -> None:
    """The worklist re-queues on a strict increase, so the strongest path wins the chain."""
    strong = build_test_fingerprint(
        "Strong",
        (build_test_pattern(ChannelEnum.HTML, "strong"),),
        implies=(build_test_implication("Shared"),),
    )
    weak = build_test_fingerprint(
        "Weak",
        (build_test_pattern(ChannelEnum.HTML, "weak", confidence=60),),
        implies=(build_test_implication("Shared"),),
    )
    shared = build_test_fingerprint("Shared", implies=(build_test_implication("Downstream"),))
    downstream = build_test_fingerprint("Downstream")
    signal = Signal(channel=ChannelEnum.HTML, value="strong and weak")

    detections = {
        detection.name: detection.confidence
        for detection in match((signal,), strong, weak, shared, downstream)
    }

    assert detections == {"Strong": 100, "Weak": 60, "Shared": 100, "Downstream": 100}


def test_match_signals_sorts_detections_regardless_of_letter_case() -> None:
    wordpress = build_test_fingerprint(
        "WordPress", (build_test_pattern(ChannelEnum.HTML, "wp-content"),)
    )
    core_js = build_test_fingerprint("core-js", (build_test_pattern(ChannelEnum.HTML, "core-js"),))
    signal = Signal(channel=ChannelEnum.HTML, value="wp-content and core-js")

    assert list_names(match((signal,), wordpress, core_js)) == ["core-js", "WordPress"]


@pytest.mark.parametrize(
    ("value_source", "key_source", "expected"),
    [
        (r"js\.stripe\.com/v3", None, r"js\.stripe\.com/v3"),
        ("", "cf-ray", "cf-ray"),
        ("nginx", "server", "server: nginx"),
    ],
    ids=["a keyless pattern", "a key with any value", "a key and a value"],
)
def test_pattern_source_text_describes_the_pattern(
    value_source: str, key_source: str | None, expected: str
) -> None:
    pattern = build_test_pattern(ChannelEnum.HEADER, value_source, key_source)

    assert pattern.decide_source_text() == expected


def test_match_signals_caps_an_implied_technology_at_the_implication_confidence() -> None:
    """Upstream writes ``PHP\\;confidence:50`` to say the implication itself is uncertain."""
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Ruby", confidence=50),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="shopify")

    detections = {detection.name: detection.confidence for detection in match((signal,), shopify)}

    assert detections == {"Shopify": 100, "Ruby": 50}


def test_match_signals_caps_an_implied_technology_at_the_implier_confidence() -> None:
    """The weaker of the two bounds wins: a shaky match cannot imply something firmly."""
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify", confidence=60),),
        implies=(build_test_implication("Ruby", confidence=80),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="shopify")

    detections = {detection.name: detection.confidence for detection in match((signal,), shopify)}

    assert detections == {"Shopify": 60, "Ruby": 60}


def test_match_signals_does_not_report_an_implication_below_the_threshold() -> None:
    shopify = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Ruby", confidence=MINIMUM_REPORTED_CONFIDENCE - 1),),
    )
    signal = Signal(channel=ChannelEnum.HTML, value="shopify")

    assert list_names(match((signal,), shopify)) == ["Shopify"]
