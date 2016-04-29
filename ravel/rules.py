from collections import defaultdict, namedtuple, Mapping, Sequence
import logging

from straight import plugin

from . import concepts
from . import predicates
from .types import Rule
from .utils.strings import get_text

logger = logging.getLogger('ravel.compilers')

plugin.load('ravel.concepts')


def compile_rulebook(rulebook):
    """Compile a rulebook declaration
    """
    rules = defaultdict(list)
    for rule_name, (concept, ruleset, *baggage) in rulebook.items():
        rule_name = get_text(rule_name)
        concept = get_text(concept)
        _, when = list(ruleset.items())[0]
        assert _.text == 'when'
        assert isinstance(when, Sequence)

        rules[concept].append(
            Rule(
                rule_name,
                predicates.compile_ruleset(
                    concept,
                    rule_name,
                    when
                ),
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
