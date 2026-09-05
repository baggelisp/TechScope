"""Grouping fingerprints into the per-channel index the matcher reads."""

import re

from techscope.domain.enums import ChannelEnum
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import Fingerprint, Pattern


def build_test_pattern(channel: ChannelEnum, source: str) -> Pattern:
    return Pattern(
        channel=channel,
        value_regex=re.compile(source, re.IGNORECASE),
        key_regex=None,
        confidence=100,
        version_template=None,
        value_source=source,
        key_source=None,
    )


def build_test_fingerprint(name: str, *patterns: Pattern) -> Fingerprint:
    return Fingerprint(name=name, patterns=patterns, implies=(), categories=())


def test_build_fingerprint_index_groups_patterns_by_channel() -> None:
    stripe = build_test_fingerprint(
        "Stripe",
        build_test_pattern(ChannelEnum.SCRIPT_SRC, "stripe"),
        build_test_pattern(ChannelEnum.HEADER, "x-stripe"),
    )

    index = build_fingerprint_index((stripe,))

    script_sources = [
        entry.pattern.value_source for entry in index.list_patterns(ChannelEnum.SCRIPT_SRC)
    ]

    assert script_sources == ["stripe"]
    header_sources = [
        entry.pattern.value_source for entry in index.list_patterns(ChannelEnum.HEADER)
    ]

    assert header_sources == ["x-stripe"]


def test_build_fingerprint_index_records_the_owning_technology() -> None:
    stripe = build_test_fingerprint("Stripe", build_test_pattern(ChannelEnum.SCRIPT_SRC, "stripe"))

    index = build_fingerprint_index((stripe,))

    assert index.list_patterns(ChannelEnum.SCRIPT_SRC)[0].technology == "Stripe"


def test_build_fingerprint_index_collects_several_technologies_in_one_channel() -> None:
    stripe = build_test_fingerprint("Stripe", build_test_pattern(ChannelEnum.SCRIPT_SRC, "stripe"))
    sentry = build_test_fingerprint("Sentry", build_test_pattern(ChannelEnum.SCRIPT_SRC, "sentry"))

    index = build_fingerprint_index((stripe, sentry))

    assert sorted(entry.technology for entry in index.list_patterns(ChannelEnum.SCRIPT_SRC)) == [
        "Sentry",
        "Stripe",
    ]


def test_build_fingerprint_index_reports_no_patterns_for_an_unused_channel() -> None:
    stripe = build_test_fingerprint("Stripe", build_test_pattern(ChannelEnum.SCRIPT_SRC, "stripe"))

    index = build_fingerprint_index((stripe,))

    assert index.list_patterns(ChannelEnum.DNS_MX) == ()


def test_build_fingerprint_index_looks_a_fingerprint_up_by_name() -> None:
    stripe = build_test_fingerprint("Stripe", build_test_pattern(ChannelEnum.SCRIPT_SRC, "stripe"))

    index = build_fingerprint_index((stripe,))

    assert index.decide_fingerprint_or_none("Stripe") is stripe


def test_build_fingerprint_index_reports_an_unknown_name_as_absent() -> None:
    index = build_fingerprint_index(())

    assert index.decide_fingerprint_or_none("Nothing") is None


def test_build_fingerprint_index_keeps_a_fingerprint_that_has_no_patterns() -> None:
    empty = build_test_fingerprint("Empty Tech")

    index = build_fingerprint_index((empty,))

    assert index.decide_fingerprint_or_none("Empty Tech") is empty


def test_build_fingerprint_index_of_nothing_is_empty() -> None:
    index = build_fingerprint_index(())

    assert index.list_patterns(ChannelEnum.HTML) == ()
