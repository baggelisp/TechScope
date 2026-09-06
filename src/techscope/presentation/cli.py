"""The command-line driver: parse arguments, read the domains file, call the composition root.

Logging goes to stderr so that stdout stays free for future machine-readable output. Argparse
values are converted into a typed record at the boundary, so no untyped ``Namespace`` attribute
travels further into the program.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path

from techscope import bootstrap
from techscope.domain.domain_list import build_domain_list
from techscope.domain.errors import FingerprintLoadError

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2

PROGRAM_NAME = "techscope"
DEFAULT_OUTPUT_PATH = "output.json"
DEFAULT_LOG_LEVEL = "WARNING"
LOG_LEVEL_CHOICES = ("DEBUG", "INFO", "WARNING", "ERROR")
LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
DOMAINS_FILE_ENCODING = "utf-8"
MINIMUM_CONCURRENCY = 1
MINIMUM_TIMEOUT_SECONDS = 0.1
MINIMUM_DEADLINE_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class ScanArguments:
    """The command line, typed. Resolved once so the rest of the module never sees ``Any``."""

    domains_path: Path
    output_path: Path
    details_path: Path | None
    fingerprints_path: Path
    nameservers: tuple[str, ...]
    concurrency: int
    timeout_seconds: float
    deadline_seconds: float
    log_level: str


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``techscope`` console script. Returns the process exit code."""
    parser = _build_parser()
    namespace = parser.parse_args(argv)
    scan_arguments = _build_scan_arguments(namespace)
    _configure_logging(scan_arguments.log_level)

    try:
        return _run_scan_command(scan_arguments)
    except FingerprintLoadError as error:
        logger.error(
            "the fingerprint database is unusable (%s): %s", error.technology, error.detail
        )

        return EXIT_USAGE
    except Exception:
        # Anything reaching here is a defect rather than a handled condition: log it with its
        # traceback for the bug report and return a code instead of propagating.
        logger.exception("unexpected failure")

        return EXIT_UNEXPECTED


def _run_scan_command(scan_arguments: ScanArguments) -> int:
    if scan_arguments.concurrency < MINIMUM_CONCURRENCY:
        logger.error(
            "--concurrency must be at least %d, got %d",
            MINIMUM_CONCURRENCY,
            scan_arguments.concurrency,
        )

        return EXIT_USAGE

    if scan_arguments.timeout_seconds < MINIMUM_TIMEOUT_SECONDS:
        logger.error(
            "--timeout must be at least %.1f seconds, got %.1f",
            MINIMUM_TIMEOUT_SECONDS,
            scan_arguments.timeout_seconds,
        )

        return EXIT_USAGE

    if scan_arguments.deadline_seconds < MINIMUM_DEADLINE_SECONDS:
        logger.error(
            "--deadline must be at least %.1f seconds, got %.1f",
            MINIMUM_DEADLINE_SECONDS,
            scan_arguments.deadline_seconds,
        )

        return EXIT_USAGE

    unusable_nameserver = _decide_unusable_nameserver_or_none(scan_arguments.nameservers)

    if unusable_nameserver is not None:
        logger.error("--nameserver %s is not an IP address", unusable_nameserver)

        return EXIT_USAGE

    text = _read_domains_text_or_none(scan_arguments.domains_path)

    if text is None:
        return EXIT_USAGE

    domains = build_domain_list(text)

    if len(domains) == 0:
        logger.error("no usable domains found in %s", scan_arguments.domains_path)

        return EXIT_USAGE

    settings = bootstrap.ScanSettings(
        fingerprints_path=scan_arguments.fingerprints_path,
        nameservers=scan_arguments.nameservers,
        concurrency=scan_arguments.concurrency,
        timeout_seconds=scan_arguments.timeout_seconds,
        deadline_seconds=scan_arguments.deadline_seconds,
    )
    options = bootstrap.ScanOptions(
        domains=domains,
        output_path=scan_arguments.output_path,
        details_path=scan_arguments.details_path,
        settings=settings,
    )
    bootstrap.run_scan(options)
    logger.info("scanned %d domains into %s", len(domains), scan_arguments.output_path)

    return EXIT_OK


def _decide_unusable_nameserver_or_none(nameservers: tuple[str, ...]) -> str | None:
    """dnspython wants addresses; a hostname there fails deep inside it as a traceback."""
    for nameserver in nameservers:
        try:
            ip_address(nameserver)
        except ValueError:
            return nameserver

    return None


def _read_domains_text_or_none(domains_path: Path) -> str | None:
    try:
        return domains_path.read_text(encoding=DOMAINS_FILE_ENCODING)
    except OSError as error:
        logger.error("cannot read the domains file %s: %s", domains_path, error)

        return None
    except UnicodeDecodeError as error:
        logger.error(
            "the domains file %s is not valid %s: %s",
            domains_path,
            DOMAINS_FILE_ENCODING,
            error,
        )

        return None


def _build_scan_arguments(namespace: argparse.Namespace) -> ScanArguments:
    domains_file: str = namespace.domains_file
    output: str = namespace.output
    details: str | None = namespace.details
    fingerprints: str = namespace.fingerprints
    nameservers: list[str] = namespace.nameserver
    concurrency: int = namespace.concurrency
    timeout: float = namespace.timeout
    deadline: float = namespace.deadline
    log_level: str = namespace.log_level

    return ScanArguments(
        domains_path=Path(domains_file),
        output_path=Path(output),
        details_path=_decide_details_path_or_none(details),
        fingerprints_path=Path(fingerprints),
        nameservers=tuple(nameservers),
        concurrency=concurrency,
        timeout_seconds=timeout,
        deadline_seconds=deadline,
        log_level=log_level,
    )


def _decide_details_path_or_none(details: str | None) -> Path | None:
    if details is None:
        return None

    return Path(details)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Detect the technologies a domain uses from public HTTP and DNS signals.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    scan = subcommands.add_parser("scan", help="scan every domain listed in a text file")
    scan.add_argument("domains_file", metavar="DOMAINS_FILE", help="one domain per line")
    scan.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"where to write the results JSON (default: {DEFAULT_OUTPUT_PATH})",
    )
    scan.add_argument(
        "--details",
        default=None,
        help="also write the evidence, problems and timings behind every result to this file",
    )
    scan.add_argument(
        "--nameserver",
        action="append",
        default=[],
        metavar="ADDRESS",
        help="DNS server to query, repeatable (default: the system resolver)",
    )
    scan.add_argument(
        "--deadline",
        type=float,
        default=bootstrap.DEFAULT_DEADLINE_SECONDS,
        help=f"seconds allowed for the whole run (default: {bootstrap.DEFAULT_DEADLINE_SECONDS})",
    )
    scan.add_argument(
        "--fingerprints",
        default=str(bootstrap.DEFAULT_FINGERPRINTS_PATH),
        help="Wappalyzer-format JSON database to match against (default: the packaged set)",
    )
    scan.add_argument(
        "--concurrency",
        type=int,
        default=bootstrap.DEFAULT_CONCURRENCY,
        help=f"domains scanned in parallel (default: {bootstrap.DEFAULT_CONCURRENCY})",
    )
    scan.add_argument(
        "--timeout",
        type=float,
        default=bootstrap.DEFAULT_TIMEOUT_SECONDS,
        help=f"seconds allowed per domain (default: {bootstrap.DEFAULT_TIMEOUT_SECONDS})",
    )
    scan.add_argument(
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default=DEFAULT_LOG_LEVEL,
        help=f"verbosity on stderr (default: {DEFAULT_LOG_LEVEL})",
    )

    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(stream=sys.stderr, level=log_level, format=LOG_FORMAT, force=True)
