r"""Refusing regexes that can be made to run for a very long time.

Fingerprints are data, and data can be hostile: a pattern is compiled from a file and then run
against pages this scanner does not control. Python's ``re`` has no timeout, so ``(a+)+$`` against
a long run of ``a`` backtracks for longer than any deadline.

A group that repeats without bound is dangerous when its body leaves the engine a choice about
which repetition consumed which characters. Three shapes do that, and the rule is narrow enough
to catch them without rejecting working fingerprints:

* **Nothing anchors one repetition against the next** — every element of the body can be skipped
  or can grow: ``(a+)+``, ``(\w+\s?)*``, ``(.*)*``, ``(a{1,}){2,}``.
* **One alternative begins with another** — a prefix can be attributed to either branch, and
  identical branches are the extreme case of that: ``(a|ab)+``, ``(a|a)+``, ``([a-z]|[a-z]{2})+``.
* **A branch can consume without bound** — it can take the next repetition's share as easily as
  its own: ``(a+|b)+``.

``(\.\d+)+`` is not dangerous and must not be rejected: the literal dot anchors each repetition,
which is why the first rule asks whether an *anchoring* element exists rather than whether a
nested quantifier does.

Two spellings of the same thing have to be read as the same thing, because a rule that catches
only one of them is a rule an attacker writes around. ``{1,}`` is ``+``; ``(?P<name>…)`` and
``(?i:…)`` are ``(?:…)`` as far as repetition risk goes.
"""

import re
from dataclasses import dataclass

GROUP_OPENER = "("
GROUP_CLOSER = ")"
ESCAPE_CHARACTER = "\\"
CLASS_OPENER = "["
CLASS_CLOSER = "]"
ALTERNATION = "|"
UNBOUNDED_QUANTIFIERS = "+*"
BOUNDED_QUANTIFIER = "?"
GROUP_MODIFIER_PREFIX = "?"
NAMED_GROUP_PREFIX = "?P<"
NAMED_GROUP_CLOSER = ">"
NAMED_BACKREFERENCE_PREFIX = "?P="
INLINE_FLAG_CHARACTERS = "aiLmsux-"
FLAG_SEPARATOR = ":"

# The group kinds that still have a body after their marker: non-capturing, look-around, atomic.
BODY_GROUP_PREFIXES = ("?:", "?=", "?!", "?<=", "?<!", "?>")

# `{2,}` repeats without a ceiling; `{2,5}` does not.
OPEN_ENDED_BRACE = re.compile(r"\{\d*,\}")
ANY_BRACE = re.compile(r"\{\d*(?:,\d*)?\}")
# `{0}`, `{0,}` and `{0,5}` may all consume nothing.
SKIPPABLE_BRACE = re.compile(r"\{0(?:,\d*)?\}")


@dataclass(frozen=True, slots=True)
class Atom:
    """One element of a pattern, and what the engine is free to do with it.

    ``is_optional`` means it may consume nothing; ``is_unbounded`` means it may consume any
    amount. Either one leaves the element unable to anchor a repetition against the next.
    """

    text: str
    is_optional: bool
    is_unbounded: bool

    @property
    def anchors_repetition(self) -> bool:
        is_free = self.is_optional or self.is_unbounded

        return not is_free


def is_pattern_safe(regex_text: str) -> bool:
    return decide_pattern_danger_or_none(regex_text) is None


def decide_pattern_danger_or_none(regex_text: str) -> str | None:
    """The offending sub-pattern, for an error a human can act on."""
    for start, end in _list_group_spans(regex_text):
        if not _repeats_without_bound(regex_text, end):
            continue

        body = _strip_group_modifier(regex_text[start + 1 : end])

        if _is_ambiguous_under_repetition(body):
            return regex_text[start : end + 1]

    return None


def _is_ambiguous_under_repetition(body: str) -> bool:
    branches = _split_alternation(body)

    if len(branches) > 1:
        return _has_overlapping_branches(branches)

    return _has_nothing_to_anchor_on(body)


def _has_nothing_to_anchor_on(body: str) -> bool:
    atoms = _list_atoms(body)

    if len(atoms) == 0:
        return False

    return not any(atom.anchors_repetition for atom in atoms)


def _has_overlapping_branches(branches: list[str]) -> bool:
    """Two ways to attribute the same characters is all the engine needs to start guessing."""
    for index, branch in enumerate(branches):
        if _consumes_without_bound(branch):
            return True

        for other in branches[index + 1 :]:
            if _is_atom_prefix(branch, other) or _is_atom_prefix(other, branch):
                return True

    return False


def _consumes_without_bound(branch: str) -> bool:
    """A branch that can grow without limit can take the next repetition's share."""
    return any(atom.is_unbounded for atom in _list_atoms(branch))


def _is_atom_prefix(shorter: str, longer: str) -> bool:
    """Element by element rather than character by character, so `[a-z]` is one thing.

    Identical branches are a prefix of each other, which is the most overlap there is.
    """
    shorter_atoms = [atom.text for atom in _list_atoms(shorter)]
    longer_atoms = [atom.text for atom in _list_atoms(longer)]

    if len(shorter_atoms) == 0 or len(shorter_atoms) > len(longer_atoms):
        return False

    return longer_atoms[: len(shorter_atoms)] == shorter_atoms


def _split_alternation(body: str) -> list[str]:
    branches: list[str] = []
    depth = 0
    start = 0
    position = 0

    while position < len(body):
        character = body[position]

        if character == ESCAPE_CHARACTER:
            position += 2

            continue

        if character == CLASS_OPENER:
            position = _decide_class_end(body, position)

            continue

        if character == GROUP_OPENER:
            depth += 1

        if character == GROUP_CLOSER:
            depth -= 1

        if character == ALTERNATION and depth == 0:
            branches.append(body[start:position])
            start = position + 1

        position += 1

    branches.append(body[start:])

    return branches


def _list_atoms(body: str) -> list[Atom]:
    """Split a branch into its top-level elements, each tagged with what may be done to it."""
    atoms: list[Atom] = []
    position = 0

    while position < len(body):
        end = _decide_atom_end(body, position)
        quantifier_end = _decide_quantifier_end(body, end)
        quantifier = body[end:quantifier_end]
        atoms.append(
            Atom(
                text=body[position:end],
                is_optional=_is_optional_quantifier(quantifier),
                is_unbounded=_is_unbounded_quantifier(quantifier),
            )
        )
        position = quantifier_end

    return atoms


def _decide_atom_end(body: str, position: int) -> int:
    character = body[position]

    if character == ESCAPE_CHARACTER:
        return min(position + 2, len(body))

    if character == CLASS_OPENER:
        return _decide_class_end(body, position)

    if character == GROUP_OPENER:
        return _decide_group_end(body, position)

    return position + 1


def _decide_quantifier_end(body: str, position: int) -> int:
    if position >= len(body):
        return position

    character = body[position]

    if character in UNBOUNDED_QUANTIFIERS or character == BOUNDED_QUANTIFIER:
        return _skip_lazy_marker(body, position + 1)

    brace = ANY_BRACE.match(body, position)

    if brace is None:
        return position

    return _skip_lazy_marker(body, brace.end())


def _skip_lazy_marker(body: str, position: int) -> int:
    if position < len(body) and body[position] == BOUNDED_QUANTIFIER:
        return position + 1

    return position


def _is_optional_quantifier(quantifier: str) -> bool:
    """Optional means the engine may consume nothing here."""
    if len(quantifier) == 0:
        return False

    if quantifier[0] in UNBOUNDED_QUANTIFIERS:
        return quantifier[0] == "*"

    if quantifier[0] == BOUNDED_QUANTIFIER:
        return True

    return SKIPPABLE_BRACE.match(quantifier) is not None


def _is_unbounded_quantifier(quantifier: str) -> bool:
    """Unbounded means the engine may consume any amount here.

    ``{1,}`` is ``+`` written differently, and a rule that reads only one of the two spellings
    is a rule that is written around rather than satisfied.
    """
    if len(quantifier) == 0:
        return False

    if quantifier[0] in UNBOUNDED_QUANTIFIERS:
        return True

    return OPEN_ENDED_BRACE.match(quantifier) is not None


def _repeats_without_bound(regex_text: str, closing_position: int) -> bool:
    following = regex_text[closing_position + 1 :]

    if following.startswith(tuple(UNBOUNDED_QUANTIFIERS)):
        return True

    return OPEN_ENDED_BRACE.match(following) is not None


def _strip_group_modifier(body: str) -> str:
    """`(?:…)`, `(?=…)`, `(?P<name>…)` and friends: the kind of group is not the risk.

    Every spelling has to reach the same analysis. A marker this does not recognise would leave
    its body unexamined, so an unknown one is reported as having no body rather than as an
    ordinary sequence of characters that happens to look harmless.
    """
    if not body.startswith(GROUP_MODIFIER_PREFIX):
        return body

    if body.startswith(NAMED_GROUP_PREFIX):
        return _strip_named_group(body)

    if body.startswith(NAMED_BACKREFERENCE_PREFIX):
        return ""

    for prefix in BODY_GROUP_PREFIXES:
        if body.startswith(prefix):
            return body[len(prefix) :]

    return _strip_inline_flags(body)


def _strip_named_group(body: str) -> str:
    closing = body.find(NAMED_GROUP_CLOSER)

    if closing == -1:
        return ""

    return body[closing + 1 :]


def _strip_inline_flags(body: str) -> str:
    """`(?i)` sets flags and has no body; `(?i:…)` sets them and then has one."""
    position = 1

    while position < len(body) and body[position] in INLINE_FLAG_CHARACTERS:
        position += 1

    if position < len(body) and body[position] == FLAG_SEPARATOR:
        return body[position + 1 :]

    return ""


def _list_group_spans(regex_text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    open_positions: list[int] = []
    position = 0

    while position < len(regex_text):
        character = regex_text[position]

        if character == ESCAPE_CHARACTER:
            position += 2

            continue

        if character == CLASS_OPENER:
            position = _decide_class_end(regex_text, position)

            continue

        if character == GROUP_OPENER:
            open_positions.append(position)

        if character == GROUP_CLOSER and len(open_positions) > 0:
            spans.append((open_positions.pop(), position))

        position += 1

    return spans


def _decide_group_end(regex_text: str, position: int) -> int:
    for start, end in _list_group_spans(regex_text):
        if start == position:
            return end + 1

    return len(regex_text)


def _decide_class_end(regex_text: str, position: int) -> int:
    index = position + 1

    while index < len(regex_text):
        if regex_text[index] == ESCAPE_CHARACTER:
            index += 2

            continue

        if regex_text[index] == CLASS_CLOSER:
            return index + 1

        index += 1

    return len(regex_text)
