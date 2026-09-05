"""The shipped database must carry the assignment's fingerprints, and only those.

The brief lists a technology, a channel label and a regex for each of its 24 patterns. Two
mapping rules turn those into shipped patterns, and this test pins both the brief and the rules,
so neither a dropped fingerprint nor a quietly widened one can ship.
"""

from dataclasses import dataclass

from techscope.domain.enums import KEYED_CHANNELS, ChannelEnum
from techscope.domain.models import Fingerprint, Pattern
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    DEFAULT_TECHNOLOGIES_PATH,
    JsonFingerprintRepository,
)

ASSIGNMENT_ROW_COUNT = 24
KEYED_PATTERN_COUNT = 5
SCRIPT_LABEL = "script"
# `gtag\(` is a call, not a URL: it can only ever appear in script text.
INLINE_ONLY_REGEXES = {r"gtag\("}
# The brief writes the Intercom cookie as `^intercom-`, meaning "a name starting with this".
# A keyed pattern names its signal end to end, so the prefix is spelled out.
SHIPPED_REGEX_BY_BRIEF_REGEX = {r"^intercom-": r"^intercom-.*"}

CHANNEL_BY_LABEL = {
    "header": ChannelEnum.HEADER,
    "cookie": ChannelEnum.COOKIE,
    "html": ChannelEnum.HTML,
    "dns_txt": ChannelEnum.DNS_TXT,
    "dns_cname": ChannelEnum.DNS_CNAME,
    "dns_mx": ChannelEnum.DNS_MX,
}


@dataclass(frozen=True, slots=True)
class AssignmentPattern:
    """One row of the brief's fingerprint table, in its own wording."""

    technology: str
    label: str
    regex: str


ASSIGNMENT_PATTERNS = [
    AssignmentPattern("HubSpot", "script", r"//js\.hs-scripts\.com/"),
    AssignmentPattern("HubSpot", "script", r"//js\.hsforms\.net/"),
    AssignmentPattern("Stripe", "script", r"js\.stripe\.com/v3"),
    AssignmentPattern("Stripe", "header", r"X-Stripe-.*"),
    AssignmentPattern("Google Analytics 4", "script", r"google-analytics\.com/g/collect"),
    AssignmentPattern("Google Analytics 4", "script", r"gtag\("),
    AssignmentPattern("Intercom", "script", r"widget\.intercom\.io/"),
    AssignmentPattern("Intercom", "cookie", r"^intercom-"),
    AssignmentPattern("Cloudflare", "header", r"cf-ray"),
    AssignmentPattern("Cloudflare", "header", r"cf-cache-status"),
    AssignmentPattern("WordPress", "html", r"/wp-content/"),
    AssignmentPattern("WordPress", "html", r"/wp-includes/"),
    AssignmentPattern("Shopify", "html", r"cdn\.shopify\.com"),
    AssignmentPattern("Shopify", "header", r"X-ShopId"),
    AssignmentPattern("SendGrid", "dns_txt", r"sendgrid\.net"),
    AssignmentPattern("HubSpot", "dns_txt", r"hubspot-developer-verification"),
    AssignmentPattern("Salesforce", "dns_cname", r"\.salesforce\.com"),
    AssignmentPattern("Google Workspace", "dns_mx", r"google\.com"),
    AssignmentPattern("Microsoft 365", "dns_mx", r"protection\.outlook\.com"),
    AssignmentPattern("Zendesk", "script", r"static\.zdassets\.com"),
    AssignmentPattern("Drift", "script", r"js\.driftt\.com"),
    AssignmentPattern("Segment", "script", r"cdn\.segment\.com/analytics\.js"),
    AssignmentPattern("Sentry", "script", r"browser\.sentry-cdn\.com"),
    AssignmentPattern("Hotjar", "script", r"static\.hotjar\.com"),
]


def decide_shipped_channels(pattern: AssignmentPattern) -> tuple[ChannelEnum, ...]:
    """Mapping rule two: the brief's `[script]` channel is the src attribute.

    Its own channel list says "HTML <script> src attributes", and a URL appearing anywhere in
    script *text* is not evidence that the script is loaded: on sentry.io, the Sentry CDN URL
    appears only inside a documentation code sample. `gtag\\(` is the exception, since a call
    can never be a src.
    """
    if pattern.label != SCRIPT_LABEL:
        return (CHANNEL_BY_LABEL[pattern.label],)

    if pattern.regex in INLINE_ONLY_REGEXES:
        return (ChannelEnum.SCRIPT_INLINE,)

    return (ChannelEnum.SCRIPT_SRC,)


def build_expected_patterns() -> list[tuple[str, ChannelEnum, str]]:
    expected: list[tuple[str, ChannelEnum, str]] = []

    for pattern in ASSIGNMENT_PATTERNS:
        regex = SHIPPED_REGEX_BY_BRIEF_REGEX.get(pattern.regex, pattern.regex)

        for channel in decide_shipped_channels(pattern):
            expected.append((pattern.technology, channel, regex))

    return expected


def load_shipped_fingerprints() -> tuple[Fingerprint, ...]:
    return JsonFingerprintRepository(DEFAULT_TECHNOLOGIES_PATH).load()


def list_shipped_patterns() -> list[tuple[str, ChannelEnum, str]]:
    return [
        (fingerprint.name, pattern.channel, decide_brief_text(pattern))
        for fingerprint in load_shipped_fingerprints()
        for pattern in fingerprint.patterns
    ]


def decide_brief_text(pattern: Pattern) -> str:
    """The regex the brief lists: the key on a keyed channel, the value otherwise."""
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


def test_the_brief_table_has_all_of_its_rows() -> None:
    assert len(ASSIGNMENT_PATTERNS) == ASSIGNMENT_ROW_COUNT


def test_shipped_database_matches_the_brief_through_the_mapping_rules() -> None:
    assert sorted(list_shipped_patterns()) == sorted(build_expected_patterns())


def test_shipped_database_contains_exactly_the_assignment_technologies() -> None:
    expected = {pattern.technology for pattern in ASSIGNMENT_PATTERNS}
    shipped = {fingerprint.name for fingerprint in load_shipped_fingerprints()}

    assert shipped == expected


def test_shipped_database_gives_every_pattern_full_confidence() -> None:
    confidences = {
        pattern.confidence
        for fingerprint in load_shipped_fingerprints()
        for pattern in fingerprint.patterns
    }

    assert confidences == {100}


def test_shipped_database_keyed_patterns_accept_any_value() -> None:
    keyed = list_keyed_patterns()

    assert len(keyed) == KEYED_PATTERN_COUNT
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
