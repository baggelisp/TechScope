"""The argparse driver: argument handling, file reading, exit codes."""

import json
from pathlib import Path

import pytest

from techscope.presentation.cli import EXIT_OK, EXIT_UNEXPECTED, EXIT_USAGE, main


def write_domains_file(directory: Path, text: str) -> Path:
    domains_file = directory / "domains.txt"
    domains_file.write_text(text, encoding="utf-8")

    return domains_file


def test_cli_scan_writes_an_empty_technology_list_for_every_domain(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "notion.so\nstripe.com\n")
    output_path = tmp_path / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(output_path)])

    assert exit_code == EXIT_OK
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "notion.so": [],
        "stripe.com": [],
    }


def test_cli_scan_normalises_and_deduplicates_the_input_file(tmp_path: Path) -> None:
    domains_file = write_domains_file(
        tmp_path, "# assignment domains\n\nhttps://www.Stripe.com/pricing\nstripe.com\nnotion.so\n"
    )
    output_path = tmp_path / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(output_path)])

    assert exit_code == EXIT_OK
    assert list(json.loads(output_path.read_text(encoding="utf-8"))) == ["stripe.com", "notion.so"]


def test_cli_scan_accepts_the_concurrency_timeout_and_log_level_flags(tmp_path: Path) -> None:
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


def test_cli_scan_unwritable_output_returns_the_unexpected_exit_code(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "stripe.com\n")
    unwritable_path = tmp_path / "absent-directory" / "output.json"

    exit_code = main(["scan", str(domains_file), "-o", str(unwritable_path)])

    assert exit_code == EXIT_UNEXPECTED


def test_cli_without_a_subcommand_exits_with_the_usage_code() -> None:
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == EXIT_USAGE


def test_cli_with_an_unknown_flag_exits_with_the_usage_code(tmp_path: Path) -> None:
    domains_file = write_domains_file(tmp_path, "stripe.com\n")

    with pytest.raises(SystemExit) as raised:
        main(["scan", str(domains_file), "--nonsense"])

    assert raised.value.code == EXIT_USAGE
