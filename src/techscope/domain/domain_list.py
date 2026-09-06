"""Building the ordered, de-duplicated scan list from what a driver was given.

Pure: the CLI reads a file and the HTTP API reads a request body, and both arrive here. Sharing
this is the point — a domain the CLI would refuse must not become a fetch because another driver
was more generous about what counts as one.
"""

import logging
from collections.abc import Iterable

from techscope.domain.domain_name import (
    decide_domain_or_none,
    decide_visible_text,
    is_ignorable_line,
)

logger = logging.getLogger(__name__)

# How much of an unusable line is quoted back. The line is someone else's text.
MAXIMUM_QUOTED_LINE_LENGTH = 80


def build_domain_list(text: str) -> tuple[str, ...]:
    """Normalise every line of a domains file, keeping input order."""
    return build_domain_list_from_lines(text.splitlines())


def build_domain_list_from_lines(lines: Iterable[str]) -> tuple[str, ...]:
    """Normalise every entry, drop the unusable ones, and de-duplicate keeping input order."""
    domains: list[str] = []
    already_listed: set[str] = set()

    for raw_line in lines:
        domain = decide_domain_or_none(raw_line)

        if domain is None:
            _log_dropped_line(raw_line)
            continue

        if domain in already_listed:
            continue

        already_listed.add(domain)
        domains.append(domain)

    return tuple(domains)


def _log_dropped_line(raw_line: str) -> None:
    """A result per input line is the promise; a line that yields none must not vanish quietly."""
    if is_ignorable_line(raw_line):
        return

    shortened = raw_line.strip()[:MAXIMUM_QUOTED_LINE_LENGTH]
    logger.warning("dropped %r: not a usable domain", decide_visible_text(shortened))
