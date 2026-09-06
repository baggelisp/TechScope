"""Normalisation of one raw input line into a scannable domain name.

Pure: no I/O, no clock, no globals. A line that carries no usable domain — blank, a comment,
a bare scheme, a hostname without a dot — resolves to ``None`` and the caller drops it.
"""

from techscope.domain.text_safety import is_visible_character

COMMENT_PREFIX = "#"
SCHEME_SEPARATOR = "://"
WWW_PREFIX = "www."
HOST_TERMINATORS = "/?#"
PORT_SEPARATOR = ":"
LABEL_SEPARATOR = "."


def decide_domain_or_none(raw_line: str) -> str | None:
    """Resolve one line of a domains file into a normalised domain, or ``None`` if unusable."""
    if is_ignorable_line(raw_line):
        return None

    line = decide_visible_text(raw_line).strip()
    lowercased = line.lower()
    without_scheme = _decide_host_without_scheme(lowercased)
    without_path = _decide_host_without_path(without_scheme)
    without_port = _decide_host_without_port(without_path)
    without_www = _decide_host_without_www(without_port)
    # Cutting a path or a trailing comment can leave the separating space behind.
    trimmed = without_www.strip()
    host = trimmed.rstrip(LABEL_SEPARATOR)

    if not _is_usable_host(host):
        return None

    return host


def is_ignorable_line(raw_line: str) -> bool:
    """Blank lines and comments are not domains and not mistakes either.

    Decided on the visible text: an editor that prepends a byte order mark puts it on line
    one, which is usually the comment header.
    """
    line = decide_visible_text(raw_line).strip()
    is_blank = len(line) == 0
    is_comment = line.startswith(COMMENT_PREFIX)

    return is_blank or is_comment


def decide_visible_text(raw_line: str) -> str:
    """A byte order mark, a NUL or a bidirectional override is not part of any domain.

    They are removed rather than refused because a reader never saw them either: a file saved
    by an editor that prepends a byte order mark still lists the domain the author typed.
    Whitespace stays, so that a tab between two words is still caught as two words.
    """
    return "".join(character for character in raw_line if _is_visible_or_space(character))


def _is_visible_or_space(character: str) -> bool:
    return character.isspace() or is_visible_character(character)


def _decide_host_without_scheme(line: str) -> str:
    separator_index = line.find(SCHEME_SEPARATOR)

    if separator_index >= 0:
        return line[separator_index + len(SCHEME_SEPARATOR) :]

    return line


def _decide_host_without_path(host: str) -> str:
    for index, character in enumerate(host):
        if character in HOST_TERMINATORS:
            return host[:index]

    return host


def _decide_host_without_port(host: str) -> str:
    separator_index = host.find(PORT_SEPARATOR)

    if separator_index >= 0:
        return host[:separator_index]

    return host


def _decide_host_without_www(host: str) -> str:
    if host.startswith(WWW_PREFIX):
        return host[len(WWW_PREFIX) :]

    return host


def _is_usable_host(host: str) -> bool:
    labels = host.split(LABEL_SEPARATOR)
    has_several_labels = len(labels) > 1
    has_empty_label = "" in labels
    has_inner_whitespace = any(character.isspace() for character in host)

    return has_several_labels and not has_empty_label and not has_inner_whitespace


def decide_apex_domain(domain: str) -> str:
    """The name to ask DNS about for this domain.

    A ``www.`` prefix is stripped, because ``www.example.com`` and ``example.com`` are the same
    organisation. Nothing else is: reducing ``blog.example.com`` to ``example.com`` requires
    knowing where the registrable domain begins, and guessing at it attributes another
    organisation's DNS to this one. ``myblog.wordpress.com`` would become ``wordpress.com``,
    whose MX records belong to Automattic, and the scan would report Automattic as this blog's
    mail provider. Without a public suffix list that guess cannot be made safely, so a domain
    below the registrable level simply returns fewer DNS signals — a miss rather than a wrong
    answer.
    """
    without_www = _decide_host_without_www(domain)

    return without_www.rstrip(LABEL_SEPARATOR)
