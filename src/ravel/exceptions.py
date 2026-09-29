from parsimonious.exceptions import ParseError as ParsimoniousParseError  # noqa: F401
from parsimonious.exceptions import VisitationError  # noqa: F401
from syml.basetypes import Source


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
        raise error_type(
            "%r" % position,
            position,
        )
    else:
        raise error_type("Could not determine source position:\n%r" % position, position)


class EvaluationError(ValueError):
    """An expression operator failed on its operands (type mismatch or arithmetic error)."""


class ConstraintError(EvaluationError):
    """A constraint could not be applied to its operand (for example, a string bound to a number)."""
