"""Building the ordered, de-duplicated scan list from the raw text of a domains file.

Pure: the caller reads the file, this module only interprets its text.
"""

from techscope.domain.domain_name import decide_domain_or_none


def build_domain_list(text: str) -> tuple[str, ...]:
    """Normalise every line, drop the unusable ones, and de-duplicate keeping input order."""
    domains: list[str] = []
    already_listed: set[str] = set()

    for raw_line in text.splitlines():
        domain = decide_domain_or_none(raw_line)

        if domain is None:
            continue

        if domain in already_listed:
            continue

        already_listed.add(domain)
        domains.append(domain)

    return tuple(domains)
