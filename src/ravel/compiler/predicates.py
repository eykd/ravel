from ravel import exceptions, parsers, types
from ravel.utils.strings import get_text


def compile_predicate(environment, target):
    try:
        comparison = parsers.ComparisonParser().parse(get_text(target))
    except (
        exceptions.ParseError,
        exceptions.ParsimoniousParseError,
        exceptions.VisitationError,
    ):
        exceptions.raise_parse_error(target, exceptions.ComparisonParseError)
    return types.Predicate(comparison.quality, comparison)
