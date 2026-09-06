"""The presenters: the one place a report or a database becomes JSON-ready records."""

from techscope.application.presenters.scan_report_presenter import present_fingerprints
from techscope.domain.enums import ChannelEnum
from tests.support.builders import (
    build_test_fingerprint,
    build_test_implication,
    build_test_pattern,
)


def test_present_fingerprints_lists_implied_technologies_by_name() -> None:
    """The API publishes names; the confidence an implication carries is the matcher's business."""
    fingerprint = build_test_fingerprint(
        "Shopify",
        (build_test_pattern(ChannelEnum.HTML, "shopify"),),
        implies=(build_test_implication("Ruby", confidence=50), build_test_implication("Rack")),
    )

    presented = present_fingerprints((fingerprint,))

    assert presented["technologies"] == [
        {"name": "Shopify", "channels": ["html"], "implies": ["Ruby", "Rack"]}
    ]


def test_present_fingerprints_sorts_technologies_by_name() -> None:
    later = build_test_fingerprint("Zendesk")
    earlier = build_test_fingerprint("Drift")

    presented = present_fingerprints((later, earlier))
    technologies = presented["technologies"]

    assert isinstance(technologies, list)
    assert [technology["name"] for technology in technologies] == ["Drift", "Zendesk"]
