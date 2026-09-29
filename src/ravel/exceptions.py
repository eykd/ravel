from dataclasses import replace

from parsimonious.exceptions import ParseError as ParsimoniousParseError  # noqa: F401
from parsimonious.exceptions import VisitationError  # noqa: F401
from syml.basetypes import Source

from ravel.utils.excerpts import ELLIPSIS, MAX_EXCERPT_LENGTH, bounded_repr, printable  # noqa: F401


class ParseError(ValueError):
    pass


class OutOfContextNodeError(ParseError):
    pass


class ComparisonParseError(ParseError):
    pass


class OperationParseError(ParseError):
    pass


class RulebookTooLargeError(ParseError):
    """A rulebook source exceeds ``environments.MAX_RULEBOOK_BYTES``."""


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
