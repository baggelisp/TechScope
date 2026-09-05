"""Loading a Wappalyzer-shaped JSON database into fingerprints."""

import json
import time
from pathlib import Path

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.domain.errors import FingerprintLoadError
from techscope.domain.models import Fingerprint
from techscope.infrastructure.repositories.json_fingerprint_repository import (
    JsonFingerprintRepository,
)

SYNTHETIC_DATABASE_SIZE = 500
SYNTHETIC_LOAD_BUDGET_SECONDS = 1.0


def write_database(directory: Path, document: object) -> Path:
    data_path = directory / "technologies.json"
    data_path.write_text(json.dumps(document), encoding="utf-8")

    return data_path


def load_one(directory: Path, name: str, definition: object) -> Fingerprint:
    data_path = write_database(directory, {name: definition})
    fingerprints = JsonFingerprintRepository(data_path).load()

    return fingerprints[0]


def list_channels(fingerprint: Fingerprint) -> list[ChannelEnum]:
    return [pattern.channel for pattern in fingerprint.patterns]


def test_repository_loads_a_technology_name(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Stripe", {"scriptSrc": r"js\.stripe\.com/v3"})

    assert fingerprint.name == "Stripe"


def test_repository_reads_a_pattern_given_as_a_plain_string(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Stripe", {"scriptSrc": r"js\.stripe\.com/v3"})

    assert [pattern.value_source for pattern in fingerprint.patterns] == [r"js\.stripe\.com/v3"]


def test_repository_reads_patterns_given_as_a_list(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "WordPress", {"html": ["/wp-content/", "/wp-includes/"]})

    assert [pattern.value_source for pattern in fingerprint.patterns] == [
        "/wp-content/",
        "/wp-includes/",
    ]


@pytest.mark.parametrize(
    ("wappalyzer_key", "expected_channel"),
    [
        ("headers", ChannelEnum.HEADER),
        ("cookies", ChannelEnum.COOKIE),
        ("meta", ChannelEnum.META),
        ("js", ChannelEnum.JS_GLOBAL),
    ],
    ids=["headers are keyed", "cookies are keyed", "meta is keyed", "js globals are keyed"],
)
def test_repository_maps_a_keyed_wappalyzer_key_to_its_channel(
    tmp_path: Path, wappalyzer_key: str, expected_channel: ChannelEnum
) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {wappalyzer_key: {"a-name": "a-value"}})

    assert list_channels(fingerprint) == [expected_channel]


@pytest.mark.parametrize(
    ("wappalyzer_key", "expected_channel"),
    [
        ("scriptSrc", ChannelEnum.SCRIPT_SRC),
        ("scripts", ChannelEnum.SCRIPT_INLINE),
        ("html", ChannelEnum.HTML),
    ],
    ids=["script src", "inline scripts", "raw html"],
)
def test_repository_maps_a_keyless_wappalyzer_key_to_its_channel(
    tmp_path: Path, wappalyzer_key: str, expected_channel: ChannelEnum
) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {wappalyzer_key: "a-pattern"})

    assert list_channels(fingerprint) == [expected_channel]


@pytest.mark.parametrize(
    ("record_type", "expected_channel"),
    [
        ("MX", ChannelEnum.DNS_MX),
        ("TXT", ChannelEnum.DNS_TXT),
        ("CNAME", ChannelEnum.DNS_CNAME),
    ],
    ids=["mail exchange", "text record", "canonical name"],
)
def test_repository_maps_each_dns_record_type_to_its_channel(
    tmp_path: Path, record_type: str, expected_channel: ChannelEnum
) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"dns": {record_type: ["a-pattern"]}})

    assert list_channels(fingerprint) == [expected_channel]


def test_repository_keeps_the_key_of_a_keyed_pattern(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Cloudflare", {"headers": {"cf-ray": ""}})
    key_regex = fingerprint.patterns[0].key_regex

    assert key_regex is not None
    assert key_regex.search("CF-RAY") is not None


def test_repository_ignores_a_wappalyzer_key_it_does_not_support(tmp_path: Path) -> None:
    definition = {"scriptSrc": "kept", "url": "ignored", "dom": "ignored", "xhr": "ignored"}

    fingerprint = load_one(tmp_path, "Some Tech", definition)

    assert [pattern.value_source for pattern in fingerprint.patterns] == ["kept"]


def test_repository_ignores_an_unsupported_dns_record_type(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"dns": {"MX": ["kept"], "SOA": ["ignored"]}})

    assert [pattern.value_source for pattern in fingerprint.patterns] == ["kept"]


def test_repository_skips_a_schema_declaration_key(tmp_path: Path) -> None:
    data_path = write_database(
        tmp_path, {"$schema": "https://example.invalid/schema.json", "Stripe": {"scriptSrc": "s"}}
    )

    fingerprints = JsonFingerprintRepository(data_path).load()

    assert [fingerprint.name for fingerprint in fingerprints] == ["Stripe"]


def test_repository_reads_implies_given_as_a_string(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"scriptSrc": "s", "implies": "PHP"})

    assert fingerprint.implies == ("PHP",)


def test_repository_reads_implies_given_as_a_list(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"scriptSrc": "s", "implies": ["PHP", "MySQL"]})

    assert fingerprint.implies == ("PHP", "MySQL")


def test_repository_strips_modifiers_from_an_implied_technology(tmp_path: Path) -> None:
    definition = {"scriptSrc": "s", "implies": r"PHP\;confidence:50"}

    fingerprint = load_one(tmp_path, "Some Tech", definition)

    assert fingerprint.implies == ("PHP",)


def test_repository_reads_categories(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"scriptSrc": "s", "cats": [10, 32]})

    assert fingerprint.categories == (10, 32)


def test_repository_without_categories_reports_none(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"scriptSrc": "s"})

    assert fingerprint.categories == ()


def test_repository_keeps_a_technology_that_has_no_usable_pattern(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"url": "only-unsupported"})

    assert fingerprint.patterns == ()


def test_repository_loads_every_technology_in_the_file(tmp_path: Path) -> None:
    document = {
        "Stripe": {"scriptSrc": "a"},
        "Shopify": {"html": "b"},
        "Sentry": {"scriptSrc": "c"},
    }
    data_path = write_database(tmp_path, document)

    fingerprints = JsonFingerprintRepository(data_path).load()

    assert sorted(fingerprint.name for fingerprint in fingerprints) == [
        "Sentry",
        "Shopify",
        "Stripe",
    ]


def test_repository_invalid_regex_names_the_technology(tmp_path: Path) -> None:
    data_path = write_database(tmp_path, {"Broken Tech": {"scriptSrc": "unclosed("}})

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology == "Broken Tech"


@pytest.mark.parametrize(
    "raw_patterns",
    [[None], [123], [{"nested": "object"}], ["valid", None]],
    ids=["a null entry", "a number entry", "an object entry", "a null beside a valid one"],
)
def test_repository_rejects_a_non_string_pattern_entry(
    tmp_path: Path, raw_patterns: list[object]
) -> None:
    data_path = write_database(tmp_path, {"Broken Tech": {"scriptSrc": raw_patterns}})

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology == "Broken Tech"


def test_repository_rejects_a_non_string_keyed_pattern_entry(tmp_path: Path) -> None:
    data_path = write_database(tmp_path, {"Broken Tech": {"headers": {"x-name": None}}})

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology == "Broken Tech"


def test_repository_rejects_malformed_implies(tmp_path: Path) -> None:
    data_path = write_database(tmp_path, {"Broken Tech": {"scriptSrc": "s", "implies": {"a": "b"}}})

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology == "Broken Tech"


def test_repository_tolerates_malformed_categories(tmp_path: Path) -> None:
    fingerprint = load_one(tmp_path, "Some Tech", {"scriptSrc": "s", "cats": "not a list"})

    assert fingerprint.categories == ()


def test_repository_missing_file_reports_a_file_level_error(tmp_path: Path) -> None:
    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(tmp_path / "absent.json").load()

    assert raised.value.technology is None


def test_repository_malformed_json_reports_a_file_level_error(tmp_path: Path) -> None:
    data_path = tmp_path / "technologies.json"
    data_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology is None


def test_repository_a_non_object_document_reports_a_file_level_error(tmp_path: Path) -> None:
    data_path = write_database(tmp_path, ["not", "an", "object"])

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology is None


def test_repository_a_non_object_technology_names_the_technology(tmp_path: Path) -> None:
    data_path = write_database(tmp_path, {"Broken Tech": "should have been an object"})

    with pytest.raises(FingerprintLoadError) as raised:
        JsonFingerprintRepository(data_path).load()

    assert raised.value.technology == "Broken Tech"


def test_repository_loads_a_full_sized_database_within_the_budget(tmp_path: Path) -> None:
    document = {
        f"Technology {index}": {
            "scriptSrc": [f"cdn{index}\\.example\\.com/a\\.js", f"cdn{index}\\.example\\.net"],
            "headers": {f"x-tech-{index}": ""},
            "html": f'<div id="tech-{index}"',
            "dns": {"TXT": [f"tech{index}-verification"]},
            "implies": "HTTP/3",
            "cats": [1, 2],
        }
        for index in range(SYNTHETIC_DATABASE_SIZE)
    }
    data_path = write_database(tmp_path, document)

    started_at = time.perf_counter()
    fingerprints = JsonFingerprintRepository(data_path).load()
    elapsed_seconds = time.perf_counter() - started_at

    assert len(fingerprints) == SYNTHETIC_DATABASE_SIZE
    assert elapsed_seconds < SYNTHETIC_LOAD_BUDGET_SECONDS
