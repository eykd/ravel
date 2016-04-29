from collections import namedtuple
import logging
import operator as op
import re

from pydash import partial_right

from . import parsers
from .types import Comparison, Predicate

logger = logging.getLogger('predicates')


def get_predicate(target):
    comparison = parsers.ComparisonParser().parse(target)
    return Predicate(comparison.quality, comparison)


def compile_ruleset(concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates.
    """
    logger.debug('Compiling predicates for %s:%s:\n%r', concept, rule_name, ruleset)
    return sorted(
        get_predicate(target)
        for target in ruleset
    )
