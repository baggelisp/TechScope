"""Writes a scan report to disk as JSON.

The shapes are decided by ``application/presenters``; this adapter only serialises them, so the
file the CLI writes cannot drift from the body the HTTP API returns.
"""

import json
import logging
from pathlib import Path

from techscope.application.presenters.scan_report_presenter import present_details, present_summary
from techscope.domain.models import ScanReport

logger = logging.getLogger(__name__)

JSON_INDENT = 2
FILE_ENCODING = "utf-8"


class JsonReportWriter:
    """Serialises deterministically: domains in input order, one trailing newline."""

    def write_summary(self, report: ScanReport, destination: Path) -> None:
        _write_json(present_summary(report), destination)
        logger.info("wrote %d domains to %s", len(report.results), destination)

    def write_details(self, report: ScanReport, destination: Path) -> None:
        _write_json(present_details(report), destination)
        logger.info("wrote the evidence for %d domains to %s", len(report.results), destination)


def _write_json(payload: object, destination: Path) -> None:
    serialised = json.dumps(payload, indent=JSON_INDENT, ensure_ascii=False)
    destination.write_text(serialised + "\n", encoding=FILE_ENCODING)
