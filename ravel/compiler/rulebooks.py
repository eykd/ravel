from collections import defaultdict, Mapping
import itertools as it

from ravel import exceptions
from ravel import types

from ravel.utils.strings import get_text

from . import concepts
from . import situations  # noqa

from .rulesets import compile_ruleset


def compile_rulebook(rulebook, prefix=''):
    """Compile a rulebook declaration
    """
    rules = defaultdict(lambda: {'rules': [], 'locations': {}})

    includes = []
    common_predicates = []

    rule = None
    rulesets = iter(rulebook.items())
    while True:
        last_rule = rule
        try:
            rule = next(rulesets)
        except StopIteration:
            raise exceptions.MissingBaggageError("No baggage found after rule: %r" % last_rule)
        else:
            key_name = get_text(rule[0])

            if key_name == 'when':
                common_predicates.extend(rule[1])
            elif key_name == 'include':
                includes.extend(get_text(rule[1]))
            else:
                # Found the baggage. Put the rule back into the iterator.
                rulesets = it.chain([rule], rulesets)
                break

    for rule_name, data in rulesets:
        if isinstance(data[0], Mapping):
            concept = 'Situation'
            ruleset = data[0]
            baggage_data = data[1:]
        else:
            concept = data[0]
            ruleset = data[1]
            baggage_data = data[2:]

        rule_name = prefix + get_text(rule_name)
        concept = get_text(concept)
        _, ruleset_predicates = list(list(ruleset.items())[0])
        assert get_text(_) == 'when', _

        rules[concept]['rules'].append(
            types.Rule(
                rule_name,
                compile_ruleset(
                    concept,
                    rule_name,
                    common_predicates + ruleset_predicates
                ),
            )
        )
        rules[concept]['locations'].update(
            concepts.compile_baggage(concept, rule_name, baggage_data)
        )

    for ruleset in rules.values():
        ruleset['rules'].sort()
    return {'rulebook': dict(rules), 'includes': includes}
