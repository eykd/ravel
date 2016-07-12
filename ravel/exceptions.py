from .types import Source


class ParseError(ValueError): pass


class OutOfContextNodeError(ParseError): pass


class ComparisonParseError(ParseError): pass


class OperationParseError(ParseError): pass


def raise_parse_error(position, error_type=ParseError):
    if isinstance(position, Source):
        raise error_type(
            "Line %s, Column %s:\n%s" % (position.start.line, position.start.column, position.text),
            position
        )
    else:
        raise error_type(
            "Could not determine source position:\n%s" % position,
            position
        )
