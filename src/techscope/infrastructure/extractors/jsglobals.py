"""JavaScript globals, found by reading script text rather than running it.

Nothing here executes anything. The script is scanned once to learn which stretches of it are
string or comment content and which are at the top level of the file, and the names are then
read only out of real code at the top level. That map is what stops a documentation snippet
inside a string from being mistaken for a script that defines the global it talks about.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass
from operator import itemgetter

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse

NEWLINE = "\n"
LINE_COMMENT_OPENER = "//"
BLOCK_COMMENT_OPENER = "/*"
BLOCK_COMMENT_CLOSER = "*/"
QUOTE_CHARACTERS = "'\"`"
ESCAPE_CHARACTER = "\\"
BLOCK_OPENER = "{"
BLOCK_CLOSER = "}"
REGEX_DELIMITER = "/"
CLASS_OPENER = "["
CLASS_CLOSER = "]"
# A slash starts a regex literal only where a value cannot already have ended. Anything in
# this set leaves the parser expecting an operand, so `/` there opens a pattern rather than
# dividing. Without this, `s.replace(/"/g, "")` opens a string at that quote and every name
# after it is read out of what the scanner then believes is text.
OPERAND_EXPECTED_AFTER = set("(,=:[!&|?{};+-*%<>~^")

NAME = r"[A-Za-z_$][\w$]*"
NOT_A_MEMBER = r"(?<![.\w$])"
ASSIGNMENT = r"\s*=(?!=)"

# `window.Shopify.shop = …` names both the path and its root; upstream keys use both forms.
WINDOW_PROPERTY = re.compile(rf"{NOT_A_MEMBER}window\.({NAME}(?:\.{NAME})*){ASSIGNMENT}")
WINDOW_SUBSCRIPT = re.compile(rf"{NOT_A_MEMBER}window\[\s*['\"]({NAME})['\"]\s*\]{ASSIGNMENT}")
DECLARATION = re.compile(rf"{NOT_A_MEMBER}(?:var|let|const)\s+({NAME}){ASSIGNMENT}")
FUNCTION_DECLARATION = re.compile(rf"{NOT_A_MEMBER}function\s+({NAME})\s*\(")

# A `window.` name is global wherever it is written; a declaration only when nothing encloses it.
GLOBAL_ANYWHERE = (WINDOW_PROPERTY, WINDOW_SUBSCRIPT)
GLOBAL_AT_TOP_LEVEL = (DECLARATION, FUNCTION_DECLARATION)

NAME_SEPARATOR = "."


@dataclass(frozen=True, slots=True)
class SpanIndex:
    """Ascending, non-overlapping character ranges, searchable in logarithmic time.

    Scanning them instead cost 397 seconds on a 2 MB script of many small assignments, because
    the work is matches multiplied by spans. The scanner emits spans in order, so a binary
    search is a drop-in replacement.
    """

    spans: tuple[tuple[int, int], ...]
    starts: tuple[int, ...]

    def contains(self, position: int) -> bool:
        index = bisect_right(self.starts, position) - 1

        if index < 0:
            return False

        return position < self.spans[index][1]


@dataclass(frozen=True, slots=True)
class CodeMap:
    """Where in a script real top-level code is, and where it is only text.

    ``ignored`` covers string literal, comment and regex-literal content. ``top_level`` covers
    the stretches outside any braces, which is where a declaration creates a global rather than
    a local.
    """

    ignored: SpanIndex
    top_level: SpanIndex

    def is_ignored(self, position: int) -> bool:
        return self.ignored.contains(position)

    def is_top_level(self, position: int) -> bool:
        return self.top_level.contains(position)


def extract_js_global_signals(response: ObservedResponse) -> tuple[Signal, ...]:
    """One signal per distinct global name, keyed by the name the way a `js` fingerprint is."""
    names: list[str] = []

    for script in response.document.inline_scripts:
        names.extend(build_javascript_globals(script))

    unique_names = tuple(dict.fromkeys(names))

    return tuple(Signal(channel=ChannelEnum.JS_GLOBAL, value="", key=name) for name in unique_names)


def build_javascript_globals(source: str) -> tuple[str, ...]:
    """The global names this script defines, in the order they first appear."""
    code_map = build_code_map(source)
    found: list[tuple[int, str]] = []

    for pattern in GLOBAL_ANYWHERE:
        found.extend(_list_names(pattern, source, code_map, require_top_level=False))

    for pattern in GLOBAL_AT_TOP_LEVEL:
        found.extend(_list_names(pattern, source, code_map, require_top_level=True))

    # By position only: a dotted path and its root share one, and the path is the fuller name.
    found.sort(key=itemgetter(0))

    return tuple(dict.fromkeys(name for _, name in found))


def build_code_map(source: str) -> CodeMap:
    """Walk the script once, recording what is text and what is top-level code."""
    ignored_spans: list[tuple[int, int]] = []
    top_level_spans: list[tuple[int, int]] = []
    depth = 0
    position = 0
    top_level_start = 0

    while position < len(source):
        skipped_to = _decide_skipped_position_or_none(source, position)

        if skipped_to is not None:
            ignored_spans.append((position, skipped_to))
            position = skipped_to

            continue

        if source[position] == BLOCK_OPENER:
            if depth == 0:
                top_level_spans.append((top_level_start, position))

            depth += 1

        if source[position] == BLOCK_CLOSER:
            depth = max(depth - 1, 0)

            if depth == 0:
                top_level_start = position

        position += 1

    if depth == 0:
        top_level_spans.append((top_level_start, len(source)))

    return CodeMap(
        ignored=_build_span_index(ignored_spans), top_level=_build_span_index(top_level_spans)
    )


def _build_span_index(spans: list[tuple[int, int]]) -> SpanIndex:
    return SpanIndex(spans=tuple(spans), starts=tuple(start for start, _ in spans))


def _decide_skipped_position_or_none(source: str, position: int) -> int | None:
    """Where a comment, string or regex literal starting here ends, or ``None`` if none does."""
    if source.startswith(LINE_COMMENT_OPENER, position):
        return _decide_line_comment_end(source, position)

    if source.startswith(BLOCK_COMMENT_OPENER, position):
        return _decide_block_comment_end(source, position)

    if source[position] in QUOTE_CHARACTERS:
        return _decide_string_end(source, position)

    if _is_regex_literal_start(source, position):
        return _decide_regex_literal_end(source, position)

    return None


def _is_regex_literal_start(source: str, position: int) -> bool:
    if source[position] != REGEX_DELIMITER:
        return False

    previous = _decide_previous_code_character_or_none(source, position)

    if previous is None:
        return True

    return previous in OPERAND_EXPECTED_AFTER


def _decide_previous_code_character_or_none(source: str, position: int) -> str | None:
    index = position - 1

    while index >= 0:
        if not source[index].isspace():
            return source[index]

        index -= 1

    return None


def _decide_regex_literal_end(source: str, position: int) -> int:
    index = position + 1
    inside_class = False

    while index < len(source):
        character = source[index]

        if character == ESCAPE_CHARACTER:
            index += 2

            continue

        if character == NEWLINE:
            return index

        if character == CLASS_OPENER:
            inside_class = True

        if character == CLASS_CLOSER:
            inside_class = False

        if character == REGEX_DELIMITER and not inside_class:
            return index + 1

        index += 1

    return len(source)


def _decide_line_comment_end(source: str, position: int) -> int:
    end = source.find(NEWLINE, position)

    if end < 0:
        return len(source)

    return end


def _decide_block_comment_end(source: str, position: int) -> int:
    end = source.find(BLOCK_COMMENT_CLOSER, position + len(BLOCK_COMMENT_OPENER))

    if end < 0:
        return len(source)

    return end + len(BLOCK_COMMENT_CLOSER)


def _decide_string_end(source: str, position: int) -> int:
    quote = source[position]
    index = position + 1

    while index < len(source):
        if source[index] == ESCAPE_CHARACTER:
            index += 2

            continue

        if source[index] == quote:
            return index + 1

        index += 1

    return len(source)


def _list_names(
    pattern: re.Pattern[str], source: str, code_map: CodeMap, require_top_level: bool
) -> list[tuple[int, str]]:
    """Each name with where it was found, so the caller can report them in reading order."""
    found: list[tuple[int, str]] = []

    for match in pattern.finditer(source):
        if not _is_usable_match(match, code_map, require_top_level):
            continue

        found.extend((match.start(), name) for name in _expand_name(match.group(1)))

    return found


def _is_usable_match(match: re.Match[str], code_map: CodeMap, require_top_level: bool) -> bool:
    """A name written inside a string or a comment is text about code, not code."""
    if code_map.is_ignored(match.start()):
        return False

    if not require_top_level:
        return True

    return code_map.is_top_level(match.start())


def _expand_name(name: str) -> list[str]:
    """``Shopify.shop`` is evidence of both itself and ``Shopify``."""
    root = name.split(NAME_SEPARATOR)[0]

    if root == name:
        return [name]

    return [name, root]
