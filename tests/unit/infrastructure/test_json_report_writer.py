"""The adapter that writes a scan report to disk, in both shapes."""

import json
from pathlib import Path

from techscope.domain.enums import BlockReasonEnum, ChannelEnum
from techscope.domain.models import (
    CollectionFailure,
    Detection,
    DomainScanResult,
    Evidence,
    ScanReport,
)
from techscope.infrastructure.writers.json_report_writer import JsonReportWriter

CLOUDFLARE_EVIDENCE = Evidence(
    channel=ChannelEnum.HEADER, key="cf-ray", pattern_source="cf-ray", matched_text="8abc-DFW"
)
BLOCKED = CollectionFailure(
    collector="http", reason=BlockReasonEnum.FORBIDDEN, detail="status 403 from https://x/"
)


def build_result(
    domain: str,
    *technologies: str,
    failures: tuple[CollectionFailure, ...] = (),
) -> DomainScanResult:
    detections = tuple(
        Detection(name=technology, confidence=100, evidence=(CLOUDFLARE_EVIDENCE,))
        for technology in technologies
    )

    return DomainScanResult(
        domain=domain,
        detections=detections,
        failures=failures,
        observed_url=f"https://{domain}/",
        duration_seconds=0.5,
    )


def build_report(*domains: str) -> ScanReport:
    results = tuple(build_result(domain) for domain in domains)

    return ScanReport(results=results, duration_seconds=1.25)


def read_json(destination: Path) -> dict[str, object]:
    """Read back what was written, narrowed rather than left untyped."""
    parsed: object = json.loads(destination.read_text(encoding="utf-8"))

    assert isinstance(parsed, dict)

    return {str(key): value for key, value in parsed.items()}


def read_summary(destination: Path) -> dict[str, object]:
    summary = read_json(destination)["summary"]

    assert isinstance(summary, dict)

    return {str(key): value for key, value in summary.items()}


def read_domains(destination: Path) -> list[dict[str, object]]:
    domains = read_json(destination)["domains"]

    assert isinstance(domains, list)

    return [entry for entry in domains if isinstance(entry, dict)]


def read_field(entry: dict[str, object], name: str) -> object:
    return entry[name]


def test_summary_writes_an_empty_list_for_a_domain_without_detections(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write_summary(build_report("stripe.com", "notion.so"), destination)

    assert read_json(destination) == {"stripe.com": [], "notion.so": []}


def test_summary_preserves_domain_order(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write_summary(
        build_report("notion.so", "stripe.com", "figma.com"), destination
    )

    assert list(read_json(destination)) == ["notion.so", "stripe.com", "figma.com"]


def test_summary_lists_the_technologies_found(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"
    report = ScanReport(
        results=(build_result("stripe.com", "Cloudflare", "Stripe"),), duration_seconds=1.0
    )

    JsonReportWriter().write_summary(report, destination)

    assert read_json(destination) == {"stripe.com": ["Cloudflare", "Stripe"]}


def test_summary_indents_and_ends_with_a_trailing_newline(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write_summary(build_report("stripe.com"), destination)

    assert destination.read_text(encoding="utf-8") == '{\n  "stripe.com": []\n}\n'


def test_summary_keeps_non_ascii_domains_unescaped(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write_summary(build_report("café.example"), destination)

    assert "café.example" in destination.read_text(encoding="utf-8")


def test_summary_overwrites_an_existing_file(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"
    destination.write_text("stale content", encoding="utf-8")

    JsonReportWriter().write_summary(build_report("stripe.com"), destination)

    assert read_json(destination) == {"stripe.com": []}


def test_summary_of_an_empty_report_writes_an_empty_object(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write_summary(ScanReport(results=(), duration_seconds=0.0), destination)

    assert read_json(destination) == {}


def test_details_records_the_run_summary(tmp_path: Path) -> None:
    destination = tmp_path / "details.json"
    report = ScanReport(results=(build_result("stripe.com", "Stripe"),), duration_seconds=1.25)

    JsonReportWriter().write_details(report, destination)

    assert read_summary(destination) == {
        "domains": 1,
        "detections": 1,
        "domains_with_problems": 0,
        "duration_seconds": 1.25,
    }


def test_details_records_the_evidence_behind_a_detection(tmp_path: Path) -> None:
    destination = tmp_path / "details.json"
    report = ScanReport(results=(build_result("stripe.com", "Cloudflare"),), duration_seconds=1.0)

    JsonReportWriter().write_details(report, destination)
    detections = read_field(read_domains(destination)[0], "detections")

    assert isinstance(detections, list)
    assert detections[0]["evidence"] == [
        {"channel": "header", "key": "cf-ray", "pattern": "cf-ray", "matched": "8abc-DFW"}
    ]


def test_details_distinguishes_a_blocked_domain_from_a_clean_one(tmp_path: Path) -> None:
    """The summary shows an empty list for both; this is where the difference lives."""
    destination = tmp_path / "details.json"
    report = ScanReport(
        results=(
            build_result("blocked.example", failures=(BLOCKED,)),
            build_result("clean.example"),
        ),
        duration_seconds=1.0,
    )

    JsonReportWriter().write_details(report, destination)
    domains = read_domains(destination)

    assert read_field(domains[0], "problems") == [
        {"collector": "http", "reason": "forbidden", "detail": "status 403 from https://x/"}
    ]
    assert read_field(domains[1], "problems") == []


def test_details_records_how_long_each_domain_took(tmp_path: Path) -> None:
    destination = tmp_path / "details.json"

    JsonReportWriter().write_details(build_report("stripe.com"), destination)

    assert read_field(read_domains(destination)[0], "duration_seconds") == 0.5


def test_details_keeps_domains_in_input_order(tmp_path: Path) -> None:
    destination = tmp_path / "details.json"

    JsonReportWriter().write_details(build_report("notion.so", "stripe.com"), destination)
    domains = read_domains(destination)

    assert [read_field(entry, "domain") for entry in domains] == ["notion.so", "stripe.com"]


def test_details_ends_with_a_trailing_newline(tmp_path: Path) -> None:
    destination = tmp_path / "details.json"

    JsonReportWriter().write_details(build_report("stripe.com"), destination)

    assert destination.read_text(encoding="utf-8").endswith("}\n")


def test_details_records_the_page_the_signals_came_from(tmp_path: Path) -> None:
    """Four of the assignment's domains redirect to the company that acquired them."""
    destination = tmp_path / "details.json"
    moved = DomainScanResult(
        domain="drift.com",
        detections=(),
        failures=(),
        observed_url="https://www.salesloft.com/platform/chat-agents",
        duration_seconds=0.4,
    )

    JsonReportWriter().write_details(
        ScanReport(results=(moved,), duration_seconds=1.0), destination
    )

    assert read_field(read_domains(destination)[0], "observed_url") == (
        "https://www.salesloft.com/platform/chat-agents"
    )
