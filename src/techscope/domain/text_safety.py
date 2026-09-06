"""Text that came from somewhere else, made safe to put in our own output.

Two paths lead outward: evidence quoted from a page, and the detail of a failure, which quotes
the target that failed. Both end up in a terminal, a JSON file and a web page, and both are
written by someone other than us.
"""

import unicodedata

# Categories that render as nothing, or as something other than themselves: NUL, terminal
# escapes, and the bidirectional overrides that let text display in an order it is not written in.
INVISIBLE_CHARACTER_CATEGORIES = frozenset({"Cc", "Cf", "Co", "Cs"})


def strip_invisible_characters(text: str) -> str:
    """Remove what a reader cannot see but a terminal or a browser would still act on."""
    return "".join(
        character
        for character in text
        if unicodedata.category(character) not in INVISIBLE_CHARACTER_CATEGORIES
    )
