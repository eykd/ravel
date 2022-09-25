import itertools as it
from collections import defaultdict
from collections.abc import Mapping

from ravel import exceptions, types
from ravel.utils.strings import get_text, is_text

from . import situations  # noqa
from . import concepts, effects
from .rulesets import compile_ruleset


def get_next(seq):
    return next(iter(seq))


def is_when(data):
    return (
        isinstance(data, Mapping)
        and len(data) == 1
        and get_text(get_next(data.keys())) == "when"
    )


def get_list_of_texts(data):
    return [get_text(data)] if is_text(data) else [get_text(t) for t in data]


def compile_givens(environment, data):
    if is_text(data):
        data = [data]
    return [op for op, _ in effects.compile_effects(environment, "", "", data)]


def compile_about(data):
    return {get_text(key): get_text(value) for key, value in data.items()}


def compile_preamble(environment, rulebook):
    includes = []
    givens = []
    common_predicates = []
    metadata = {}

    rule = None
    rulesets = iter(rulebook.items())
    while True:
        last_rule = rule
        try:
            rule = next(rulesets)
        except StopIteration:
            raise exceptions.MissingBaggageError(
                "No baggage found after rule: %r" % last_rule
            )
        else:
            key_name = get_text(rule[0])

            if key_name == "when":
                common_predicates.extend(get_list_of_texts(rule[1]))
            elif key_name == "include":
                includes.extend(get_list_of_texts(rule[1]))
            elif key_name == "given":
                givens.extend(compile_givens(environment, rule[1]))
            elif key_name == "about":
                metadata.update(compile_about(rule[1]))
            else:
                # Found the baggage. Put the rule back into the iterator.
                rulesets = it.chain([rule], rulesets)
                break

    return {
        "includes": includes,
        "givens": givens,
        "common_predicates": common_predicates,
        "metadata": metadata,
        "rulesets": rulesets,
    }


def compile_rulebook(environment, rulebook, prefix=""):
    """Compile a rulebook declaration"""
    rules = defaultdict(lambda: {"rules": [], "locations": {}})

    preamble = compile_preamble(environment, rulebook)

    for rule_name, data in preamble["rulesets"]:
        if is_when(data[0]):
            concept = "Situation"
            ruleset_predicates = get_list_of_texts(get_next(data[0].values()))
            baggage_data = data[1:]
        elif len(data) > 1 and is_when(data[1]):
            concept = data[0]
            ruleset_predicates = get_list_of_texts(get_next(data[1].values()))
            baggage_data = data[2:]
        else:
            concept = "Situation"
            ruleset_predicates = []
            baggage_data = data[:]

        rule_name = prefix + get_text(rule_name)
        concept = get_text(concept)

        rules[concept]["rules"].append(
            types.Rule(
                rule_name,
                compile_ruleset(
                    environment,
                    concept,
                    rule_name,
                    preamble["common_predicates"] + ruleset_predicates,
                ),
            )
        )
        rules[concept]["locations"].update(
            concepts.compile_baggage(environment, concept, rule_name, baggage_data)
        )

    for ruleset in rules.values():
        ruleset["rules"].sort()

    return {
        "rulebook": dict(rules),
        "includes": preamble["includes"],
        "givens": preamble["givens"],
        "metadata": preamble["metadata"],
    }
