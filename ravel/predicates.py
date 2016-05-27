from collections import namedtuple

from parsimonious import ParseError, VisitationError

from .exceptions import ComparisonParseError
from .comparisons import ComparisonParser
from .types import Source
from .utils.strings import get_text


Predicate = namedtuple('Predicate', ['name', 'predicate'])


def get_predicate(target):
    try:
        comparison = ComparisonParser().parse(get_text(target))
    except (ParseError, VisitationError):
        if isinstance(target, Source):
            raise ComparisonParseError(
                "Line %s, Column %s:\n%s" % (target.start.line, target.start.column, target.text),
                target
            )
        else:
            raise ComparisonParseError(
                "Could not determine source position:\n%s" % target,
                target
            )
    return Predicate(comparison.quality, comparison)


def compile_ruleset(concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates.
    """
    return sorted(
        get_predicate(target)
        for target in ruleset
    )
