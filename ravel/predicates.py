from collections import namedtuple

from parsimonious import ParseError, VisitationError

from . import exceptions
from .comparisons import ComparisonParser
from .types import Source
from .utils.strings import get_text


BasePredicate = namedtuple('Predicate', ['name', 'predicate'])


class Predicate(BasePredicate):
    __slots__ = ()

    def __repr__(self):
        return '{%s: %r}' % (self.name, self.predicate)


def get_predicate(target):
    try:
        comparison = ComparisonParser().parse(get_text(target))
    except (ParseError, VisitationError):
        exceptions.raise_parse_error(target, exceptions.ComparisonParseError)
    return Predicate(comparison.quality, comparison)


def compile_ruleset(concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates.
    """
    return sorted(
        get_predicate(target)
        for target in ruleset
    )
