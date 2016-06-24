from collections import defaultdict, namedtuple

from straight import plugin

from . import concepts
from . import predicates
from .utils.strings import get_text

RuleBase = namedtuple('Rule', ['name', 'predicates'])


class Rule(RuleBase):
    __slots__ = ()


plugin.load('ravel.concepts')


def compile_rulebook(rulebook):
    """Compile a rulebook declaration
    """
    rules = defaultdict(lambda: {'rules': [], 'locations': {}})

    common_predicates = []

    rulesets = list(rulebook.items())
    if rulesets and get_text(rulesets[0][0]) == 'when':
        _, common_predicates = rulesets.pop(0)

    for rule_name, (concept, ruleset, *baggage) in rulesets:
        rule_name = get_text(rule_name)
        concept = get_text(concept)
        _, ruleset_predicates = list(list(ruleset.items())[0])
        assert _.text == 'when'

        rules[concept]['rules'].append(
            Rule(
                rule_name,
                predicates.compile_ruleset(
                    concept,
                    rule_name,
                    common_predicates + ruleset_predicates
                ),
            )
        )
        rules[concept]['locations'].update(compile_baggage(concept, rule_name, baggage))

    for ruleset in rules.values():
        ruleset['rules'].sort()
    return dict(rules)


def compile_baggage(concept, rule_name, baggage):
    """Compile the given baggage using a registered concept handler.
    """
    return concepts.get_handler_for(concept)(concept, rule_name, baggage)
