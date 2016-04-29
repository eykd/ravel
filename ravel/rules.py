from collections import defaultdict, namedtuple
import logging

from straight import plugin

from . import concepts
from . import predicates
from .types import Rule

logger = logging.getLogger('ravel.compilers')

plugin.load('ravel.concepts')


def compile_rulebook(rulebook):
    """Compile a rulebook declaration
    """
    rules = defaultdict(list)
    for rule_name, (concept, ruleset, *baggage) in rulebook.items():
        rules[concept].append(
            Rule(
                rule_name,
                predicates.compile_ruleset(concept, rule_name, ruleset.get('when', {})),
                compile_baggage(concept, rule_name, baggage),
            )
        )
    for ruleset in rules.values():
        ruleset.sort()
    return dict(rules)


def compile_baggage(concept, rule_name, baggage):
    """Compile the given baggage using a registered concept handler.
    """
    return concepts.get_handler_for(concept)(concept, rule_name, baggage)
