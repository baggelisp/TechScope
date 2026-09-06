"""Parsing one Wappalyzer pattern string into a compiled Pattern."""

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.domain.errors import FingerprintLoadError
from techscope.domain.models import Implication, Pattern
from techscope.infrastructure.repositories.wappalyzer_pattern import (
    DEFAULT_CONFIDENCE,
    build_implication,
    build_pattern,
)


def build_script_pattern(raw_pattern: str) -> Pattern:
    return build_pattern("Stripe", ChannelEnum.SCRIPT_SRC, raw_pattern, None)


def test_build_pattern_keeps_the_regex_and_the_original_source() -> None:
    pattern = build_script_pattern(r"js\.stripe\.com/v3")

    assert pattern.value_source == r"js\.stripe\.com/v3"
    assert pattern.value_regex.search("https://js.stripe.com/v3/") is not None


def test_build_pattern_matches_case_insensitively() -> None:
    pattern = build_script_pattern(r"js\.stripe\.com/v3")

    assert pattern.value_regex.search("HTTPS://JS.STRIPE.COM/V3/") is not None


def test_build_pattern_defaults_the_confidence_to_full() -> None:
    pattern = build_script_pattern(r"js\.stripe\.com/v3")

    assert pattern.confidence == DEFAULT_CONFIDENCE


def test_build_pattern_reads_the_confidence_modifier() -> None:
    pattern = build_script_pattern(r"js\.stripe\.com/v3\;confidence:50")

    assert pattern.confidence == 50
    assert pattern.value_source == r"js\.stripe\.com/v3"


def test_build_pattern_strips_the_confidence_modifier_from_the_regex() -> None:
    pattern = build_script_pattern(r"js\.stripe\.com/v3\;confidence:50")

    assert pattern.value_regex.search("js.stripe.com/v3") is not None
    assert pattern.value_regex.search("confidence:50") is None


def test_build_pattern_reads_the_version_modifier() -> None:
    pattern = build_script_pattern(r"jquery-(\d+\.\d+)\.js\;version:\1")

    assert pattern.version_template == r"\1"


def test_build_pattern_reads_confidence_and_version_together() -> None:
    pattern = build_script_pattern(r"analytics\.js\;confidence:75\;version:\1")

    assert pattern.confidence == 75
    assert pattern.version_template == r"\1"
    assert pattern.value_source == r"analytics\.js"


def test_build_pattern_without_a_version_modifier_has_no_version() -> None:
    pattern = build_script_pattern(r"analytics\.js")

    assert pattern.version_template is None


def test_build_pattern_ignores_an_unknown_modifier() -> None:
    pattern = build_script_pattern(r"analytics\.js\;nonsense:7")

    assert pattern.confidence == DEFAULT_CONFIDENCE
    assert pattern.value_source == r"analytics\.js"


def test_build_pattern_empty_value_on_a_keyed_channel_matches_any_value() -> None:
    pattern = build_pattern("Cloudflare", ChannelEnum.HEADER, "", "cf-ray")

    assert pattern.value_regex.search("anything at all") is not None
    assert pattern.value_regex.search("") is not None


def test_build_pattern_empty_value_on_a_keyless_channel_is_rejected() -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_pattern("Broken Tech", ChannelEnum.HTML, "", None)

    assert raised.value.technology == "Broken Tech"


def test_build_pattern_keyless_channel_has_no_key_regex() -> None:
    pattern = build_script_pattern(r"analytics\.js")

    assert pattern.key_regex is None


def test_build_pattern_keyed_channel_compiles_the_key_as_a_regex() -> None:
    pattern = build_pattern("Stripe", ChannelEnum.HEADER, "", "X-Stripe-.*")

    assert pattern.key_regex is not None
    assert pattern.key_regex.search("x-stripe-account") is not None
    assert pattern.key_regex.search("x-shopid") is None


def test_build_pattern_records_the_channel() -> None:
    pattern = build_pattern("Cloudflare", ChannelEnum.HEADER, "", "cf-ray")

    assert pattern.channel is ChannelEnum.HEADER


def test_build_pattern_invalid_regex_names_the_technology() -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_pattern("Broken Tech", ChannelEnum.SCRIPT_SRC, "unclosed(", None)

    assert raised.value.technology == "Broken Tech"


def test_build_pattern_invalid_key_regex_names_the_technology() -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_pattern("Broken Tech", ChannelEnum.HEADER, "", "unclosed(")

    assert raised.value.technology == "Broken Tech"


def test_build_pattern_non_numeric_confidence_names_the_technology() -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_pattern("Broken Tech", ChannelEnum.SCRIPT_SRC, r"a\;confidence:high", None)

    assert raised.value.technology == "Broken Tech"


@pytest.mark.parametrize("confidence_text", ["-1", "101"], ids=["below zero", "above one hundred"])
def test_build_pattern_confidence_outside_the_range_is_rejected(confidence_text: str) -> None:
    with pytest.raises(FingerprintLoadError):
        raw_pattern = rf"a\;confidence:{confidence_text}"
        build_pattern("Broken Tech", ChannelEnum.SCRIPT_SRC, raw_pattern, None)


def test_build_implication_gives_a_plain_name_full_confidence() -> None:
    assert build_implication("Some Tech", "PHP") == Implication(technology="PHP", confidence=100)


def test_build_implication_reads_a_confidence_modifier() -> None:
    assert build_implication("Some Tech", r"PHP\;confidence:50") == Implication(
        technology="PHP", confidence=50
    )


def test_build_implication_trims_surrounding_whitespace() -> None:
    assert build_implication("Some Tech", "  PHP  ").technology == "PHP"


def test_build_implication_rejects_a_confidence_that_is_not_a_number() -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        build_implication("Some Tech", r"PHP\;confidence:high")

    assert raised.value.technology == "Some Tech"


@pytest.mark.parametrize(
    "raw_implies", ["", "   ", r"\;confidence:50"], ids=["empty", "blank", "a modifier alone"]
)
def test_build_implication_rejects_an_entry_without_a_name(raw_implies: str) -> None:
    """An implication is reported as a detection, and a detection with no name is not one."""
    with pytest.raises(FingerprintLoadError) as raised:
        build_implication("Some Tech", raw_implies)

    assert raised.value.technology == "Some Tech"
