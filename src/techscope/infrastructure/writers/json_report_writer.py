"""Writes the assignment's output shape: ``{ "<domain>": [technologies] }``."""

import json
import logging
from pathlib import Path

from techscope.domain.models import ScanReport

logger = logging.getLogger(__name__)

JSON_INDENT = 2
FILE_ENCODING = "utf-8"


class JsonReportWriter:
    """Serialises a report deterministically: domains in input order, one trailing newline."""

    def write(self, report: ScanReport, destination: Path) -> None:
        payload = {result.domain: list(result.technologies) for result in report.results}
        serialised = json.dumps(payload, indent=JSON_INDENT, ensure_ascii=False)
        destination.write_text(serialised + "\n", encoding=FILE_ENCODING)
        logger.info("wrote %d domains to %s", len(payload), destination)
