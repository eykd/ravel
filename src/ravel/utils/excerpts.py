"""Bounded, printable-escaped excerpts of untrusted text for error messages.

Dependency-free utility usable from any layer of ravel without pulling in
heavy dependencies like parsimonious or syml.
"""

MAX_EXCERPT_LENGTH = 80
ELLIPSIS = "…"


def printable(text: object, limit: int = MAX_EXCERPT_LENGTH) -> str:
    """Render ``text`` as a bounded, printable-escaped excerpt safe to put in a message.

    Text longer than ``limit`` code points is cut and marked with an ellipsis; non-printable
    characters (control characters, ANSI escapes, lone surrogates) are backslash-escaped. Short
    printable text comes back unchanged.
    """
    shown = str(text)
    if len(shown) > limit:
        shown = shown[:limit] + ELLIPSIS
    if shown.isprintable():
        return shown
    return "".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii") for char in shown)


def bounded_repr(value: object, limit: int = MAX_EXCERPT_LENGTH) -> str:
    """Return ``repr(value)`` as a bounded, printable-escaped excerpt (see ``printable``)."""
    return printable(repr(value), limit)
