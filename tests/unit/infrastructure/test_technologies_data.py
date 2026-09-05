"""The shipped fingerprint database must carry exactly the assignment's 24 patterns.

The assignment lists technology, channel and regex for each. This test pins all three, so a
later edit to the data file cannot silently drop or alter a required fingerprint.
"""

from techscope.domain.enums import KEYED_CHANNELS, ChannelEnum
from techscope.domain.models import Fingerprint, Pattern
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)

# (technology, channel, pattern source) exactly as the assignment brief lists them. Two mapping
# decisions are recorded in the design spec: an assignment [script] pattern becomes a scriptSrc
# pattern, except `gtag\(` which can only occur in inline script text; and an assignment
# [header] or [cookie] pattern names the header or cookie rather than constraining its value,
# so it becomes the pattern's key.
ASSIGNMENT_PATTERNS = [
    ("HubSpot", ChannelEnum.SCRIPT_SRC, r"//js\.hs-scripts\.com/"),
    ("HubSpot", ChannelEnum.SCRIPT_SRC, r"//js\.hsforms\.net/"),
    ("HubSpot", ChannelEnum.DNS_TXT, r"hubspot-developer-verification"),
    ("Stripe", ChannelEnum.SCRIPT_SRC, r"js\.stripe\.com/v3"),
    ("Stripe", ChannelEnum.HEADER, r"X-Stripe-.*"),
    ("Google Analytics 4", ChannelEnum.SCRIPT_SRC, r"google-analytics\.com/g/collect"),
    ("Google Analytics 4", ChannelEnum.SCRIPT_INLINE, r"gtag\("),
    ("Intercom", ChannelEnum.SCRIPT_SRC, r"widget\.intercom\.io/"),
    # The brief writes this as `^intercom-`; the trailing `.*` spells out the prefix that
    # was already meant, because a keyed pattern must name the signal end to end.
    ("Intercom", ChannelEnum.COOKIE, r"^intercom-.*"),
    ("Cloudflare", ChannelEnum.HEADER, r"cf-ray"),
    ("Cloudflare", ChannelEnum.HEADER, r"cf-cache-status"),
    ("WordPress", ChannelEnum.HTML, r"/wp-content/"),
    ("WordPress", ChannelEnum.HTML, r"/wp-includes/"),
    ("Shopify", ChannelEnum.HTML, r"cdn\.shopify\.com"),
    ("Shopify", ChannelEnum.HEADER, r"X-ShopId"),
    ("SendGrid", ChannelEnum.DNS_TXT, r"sendgrid\.net"),
    ("Salesforce", ChannelEnum.DNS_CNAME, r"\.salesforce\.com"),
    ("Google Workspace", ChannelEnum.DNS_MX, r"google\.com"),
    ("Microsoft 365", ChannelEnum.DNS_MX, r"protection\.outlook\.com"),
    ("Zendesk", ChannelEnum.SCRIPT_SRC, r"static\.zdassets\.com"),
    ("Drift", ChannelEnum.SCRIPT_SRC, r"js\.driftt\.com"),
    ("Segment", ChannelEnum.SCRIPT_SRC, r"cdn\.segment\.com/analytics\.js"),
    ("Sentry", ChannelEnum.SCRIPT_SRC, r"browser\.sentry-cdn\.com"),
    ("Hotjar", ChannelEnum.SCRIPT_SRC, r"static\.hotjar\.com"),
]

# cf-ray, cf-cache-status, X-ShopId, X-Stripe-.* and ^intercom-.
KEYED_PATTERN_COUNT = 5


def load_shipped_fingerprints() -> tuple[Fingerprint, ...]:
    return JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()


def list_shipped_patterns() -> list[tuple[str, ChannelEnum, str]]:
    shipped: list[tuple[str, ChannelEnum, str]] = []

    for fingerprint in load_shipped_fingerprints():
        for pattern in fingerprint.patterns:
            shipped.append((fingerprint.name, pattern.channel, decide_assignment_text(pattern)))

    return shipped


def decide_assignment_text(pattern: Pattern) -> str:
    """The regex the assignment lists: the key on a keyed channel, the value otherwise."""
    if pattern.channel in KEYED_CHANNELS:
        return decide_key_source(pattern)

    return pattern.value_source


def decide_key_source(pattern: Pattern) -> str:
    if pattern.key_source is None:
        return "<missing key>"

    return pattern.key_source


def list_keyed_patterns() -> list[Pattern]:
    return [
        pattern
        for fingerprint in load_shipped_fingerprints()
        for pattern in fingerprint.patterns
        if pattern.channel in KEYED_CHANNELS
    ]


def test_shipped_database_contains_every_assignment_pattern() -> None:
    assert sorted(list_shipped_patterns()) == sorted(ASSIGNMENT_PATTERNS)


def test_shipped_database_contains_exactly_the_assignment_technologies() -> None:
    expected = {technology for technology, _, _ in ASSIGNMENT_PATTERNS}
    shipped = {fingerprint.name for fingerprint in load_shipped_fingerprints()}

    assert shipped == expected


def test_shipped_database_gives_every_pattern_full_confidence() -> None:
    confidences = {
        pattern.confidence
        for fingerprint in load_shipped_fingerprints()
        for pattern in fingerprint.patterns
    }

    assert confidences == {100}


def test_shipped_database_has_the_expected_number_of_keyed_patterns() -> None:
    assert len(list_keyed_patterns()) == KEYED_PATTERN_COUNT


def test_shipped_database_keyed_patterns_accept_any_value() -> None:
    keyed = list_keyed_patterns()

    assert [pattern.value_source for pattern in keyed] == [""] * KEYED_PATTERN_COUNT


def test_shipped_database_keyed_patterns_all_carry_a_key() -> None:
    keyed = list_keyed_patterns()

    assert [pattern.key_source is None for pattern in keyed] == [False] * KEYED_PATTERN_COUNT


def test_shipped_database_declares_no_implied_technologies() -> None:
    implied = {
        implication
        for fingerprint in load_shipped_fingerprints()
        for implication in fingerprint.implies
    }

    assert implied == set()
