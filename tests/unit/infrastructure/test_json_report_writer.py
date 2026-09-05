"""The adapter that writes the assignment's output shape to disk."""

import json
from pathlib import Path

from techscope.domain.models import DomainScanResult, ScanReport
from techscope.infrastructure.writers.json_report_writer import JsonReportWriter


def build_report(*domains: str) -> ScanReport:
    results = tuple(DomainScanResult(domain=domain, technologies=()) for domain in domains)

    return ScanReport(results=results)


def test_json_report_writer_writes_an_empty_list_for_every_domain(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write(build_report("stripe.com", "notion.so"), destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "stripe.com": [],
        "notion.so": [],
    }


def test_json_report_writer_preserves_domain_order(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write(build_report("notion.so", "stripe.com", "figma.com"), destination)

    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert list(payload) == ["notion.so", "stripe.com", "figma.com"]


def test_json_report_writer_serialises_technologies_as_a_list(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"
    report = ScanReport(
        results=(DomainScanResult(domain="stripe.com", technologies=("Cloudflare", "Stripe")),)
    )

    JsonReportWriter().write(report, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "stripe.com": ["Cloudflare", "Stripe"]
    }


def test_json_report_writer_indents_and_ends_with_a_trailing_newline(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write(build_report("stripe.com"), destination)

    assert destination.read_text(encoding="utf-8") == '{\n  "stripe.com": []\n}\n'


def test_json_report_writer_keeps_non_ascii_domains_unescaped(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write(build_report("café.example"), destination)

    assert "café.example" in destination.read_text(encoding="utf-8")


def test_json_report_writer_overwrites_an_existing_file(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"
    destination.write_text("stale content", encoding="utf-8")

    JsonReportWriter().write(build_report("stripe.com"), destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {"stripe.com": []}


def test_json_report_writer_writes_an_empty_object_for_an_empty_report(tmp_path: Path) -> None:
    destination = tmp_path / "output.json"

    JsonReportWriter().write(ScanReport(results=()), destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {}
