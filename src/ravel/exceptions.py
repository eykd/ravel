from dataclasses import replace

from parsimonious.exceptions import ParseError as ParsimoniousParseError  # noqa: F401
from parsimonious.exceptions import VisitationError  # noqa: F401
from syml.basetypes import Source

MAX_EXCERPT_LENGTH = 80
ELLIPSIS = "\u2026"


def printable(text, limit=MAX_EXCERPT_LENGTH):
    """Render ``text`` as a bounded, printable-escaped excerpt safe to put in a message.

    Text longer than ``limit`` code points is cut and marked with an ellipsis; non-printable
    characters (control characters, ANSI escapes, lone surrogates) are backslash-escaped. Short
    printable text comes back unchanged.
    """
    text = str(text)
    if len(text) > limit:
        text = text[:limit] + ELLIPSIS
    if text.isprintable():
        return text
    return "".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii") for char in text)


def bounded_repr(value, limit=MAX_EXCERPT_LENGTH):
    """Return ``repr(value)`` as a bounded, printable-escaped excerpt (see ``printable``)."""
    return printable(repr(value), limit)


class ParseError(ValueError):
    pass


class OutOfContextNodeError(ParseError):
    pass


class ComparisonParseError(ParseError):
    pass


class OperationParseError(ParseError):
    pass


class RulebookTooLargeError(ParseError):
    """A rulebook source exceeds ``loaders.MAX_RULEBOOK_BYTES``."""


class MissingBaggageError(Exception):
    pass


class RulebookNotFound(Exception):
    pass


def raise_parse_error(position, error_type=ParseError):
    if isinstance(position, Source):
        shown = (
            replace(position, text=position.text[:MAX_EXCERPT_LENGTH] + ELLIPSIS)
            if len(position.text) > MAX_EXCERPT_LENGTH
            else position
        )
        raise error_type(
            "%r" % shown,
            position,
        )
    else:
        raise error_type("Could not determine source position:\n%s" % bounded_repr(position), position)


class EvaluationError(ValueError):
    """An expression operator failed on its operands (type mismatch or arithmetic error)."""


class ConstraintError(EvaluationError):
    """A constraint could not be applied to its operand (for example, a string bound to a number)."""
