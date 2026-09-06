"""The argparse driver: argument handling, file reading, exit codes.

Every scan here runs through the real fetch path, so every test mocks the transport. A unit
test that reaches the internet is a bug.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from techscope.presentation.cli import EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, main


def mock_every_host() -> None:
    """Any homepage answers with a page that matches no fingerprint."""
    respx.route().mock(return_value=httpx.Response(200, text="<html><body>ok</body></html>"))


def write_domains_file(directory: Path, text: str) -> Path:
    domains_file = directory / "domains.txt"
    domains_file.write_text(text, encoding="utf-8")

    return domains_file


@respx.mock
def test_cli_scan_writes_an_empty_technology_list_for_every_domain(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "notion.so\nstripe.com\n")
    output_path = tmp_path / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(output_path)])

    assert exit_code == EXIT_OK
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "notion.so": [],
        "stripe.com": [],
    }


@respx.mock
def test_cli_scan_normalises_and_deduplicates_the_input_file(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(
        tmp_path, "# assignment domains\n\nhttps://www.Stripe.com/pricing\nstripe.com\nnotion.so\n"
    )
    output_path = tmp_path / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(output_path)])

    assert exit_code == EXIT_OK
    assert list(json.loads(output_path.read_text(encoding="utf-8"))) == ["stripe.com", "notion.so"]


@respx.mock
def test_cli_scan_accepts_the_concurrency_timeout_and_log_level_flags(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    output_path = tmp_path / "output.json"

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(output_path),
            "--concurrency",
            "4",
            "--timeout",
            "7.5",
            "--log-level",
            "INFO",
        ]
    )

    assert exit_code == EXIT_OK
    assert output_path.exists()


def test_cli_scan_missing_input_file_returns_the_usage_exit_code(tmp_path: Path) -> None:
    missing_file = tmp_path / "absent.txt"

    exit_code = main(["scan", str(missing_file), "-o", str(tmp_path / "output.json")])

    assert exit_code == EXIT_USAGE


def test_cli_scan_missing_input_file_writes_no_output(tmp_path: Path) -> None:
    output_path = tmp_path / "output.json"

    main(["scan", str(tmp_path / "absent.txt"), "-o", str(output_path)])

    assert not output_path.exists()


def test_cli_scan_undecodable_input_file_returns_the_usage_exit_code(tmp_path: Path) -> None:
    domains_file = tmp_path / "domains.txt"
    domains_file.write_bytes(b"caf\xe9.example\n")

    exit_code = main(["scan", str(domains_file), "-o", str(tmp_path / "output.json")])

    assert exit_code == EXIT_USAGE


def test_cli_scan_file_without_usable_domains_returns_the_usage_exit_code(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "# only a comment\n\n   \n")

    exit_code = main(["scan", str(domains_file), "-o", str(tmp_path / "output.json")])

    assert exit_code == EXIT_USAGE


@respx.mock
def test_cli_scan_unwritable_output_returns_the_unexpected_exit_code(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    unwritable_path = tmp_path / "absent-directory" / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(unwritable_path)])

    assert exit_code == EXIT_UNEXPECTED


def test_cli_scan_broken_fingerprint_database_returns_the_usage_exit_code(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    fingerprints_file = tmp_path / "technologies.json"
    fingerprints_file.write_text('{"Broken Tech": {"scriptSrc": "unclosed("}}', encoding="utf-8")

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(tmp_path / "output.json"),
            "--fingerprints",
            str(fingerprints_file),
        ]
    )

    assert exit_code == EXIT_USAGE


@respx.mock
def test_cli_scan_accepts_an_alternative_fingerprint_database(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    fingerprints_file = tmp_path / "technologies.json"
    fingerprints_file.write_text('{"Some Tech": {"scriptSrc": "a"}}', encoding="utf-8")
    output_path = tmp_path / "output.json"

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(output_path),
            "--fingerprints",
            str(fingerprints_file),
        ]
    )

    assert exit_code == EXIT_OK
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"stripe.com": []}


def test_cli_without_a_subcommand_exits_with_the_usage_code() -> None:
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == EXIT_USAGE


def test_cli_with_an_unknown_flag_exits_with_the_usage_code(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    with pytest.raises(SystemExit) as raised:
        main(["scan", str(domains_file), "--nonsense"])

    assert raised.value.code == EXIT_USAGE


@respx.mock
def test_cli_scan_writes_the_details_file_when_asked(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    details_path = tmp_path / "details.json"

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(tmp_path / "output.json"),
            "--details",
            str(details_path),
        ]
    )

    assert exit_code == EXIT_OK
    assert "summary" in json.loads(details_path.read_text(encoding="utf-8"))


@respx.mock
def test_cli_scan_writes_no_details_file_by_default(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    main(["scan", str(domains_file), "-o", str(tmp_path / "output.json")])

    assert list(tmp_path.glob("*details*")) == []


def test_cli_scan_rejects_a_deadline_below_the_minimum(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    exit_code = main(
        ["scan", str(domains_file), "-o", str(tmp_path / "output.json"), "--deadline", "0"]
    )

    assert exit_code == EXIT_USAGE


def test_cli_scan_rejects_a_nameserver_that_is_not_an_address(tmp_path: Path) -> None:
    """dnspython wants addresses; a hostname there fails deep inside it as a traceback."""
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(tmp_path / "output.json"),
            "--nameserver",
            "not-a-server",
        ]
    )

    assert exit_code == EXIT_USAGE


@respx.mock
def test_cli_scan_accepts_a_nameserver_address(tmp_path: Path) -> None:
    mock_every_host()
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    exit_code = main(
        [
            "scan",
            str(domains_file),
            "-o",
            str(tmp_path / "output.json"),
            "--nameserver",
            "1.1.1.1",
        ]
    )

    assert exit_code == EXIT_OK
