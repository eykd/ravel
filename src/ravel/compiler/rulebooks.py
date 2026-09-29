import heapq
import itertools as it
from collections import defaultdict
from collections.abc import Mapping

from ravel import exceptions, types
from ravel.utils.strings import get_text, is_text

from . import (
    concepts,
    effects,
    situations,  # noqa
)
from .rulesets import compile_ruleset


def get_next(seq):
    return next(iter(seq))


def is_when(data):
    return isinstance(data, Mapping) and len(data) == 1 and get_text(get_next(data.keys())) == "when"


def get_list_of_texts(data):
    return [get_text(data)] if is_text(data) else [get_text(t) for t in data]


def get_list_of_sources(data):
    """Like get_list_of_texts, but keep syml Source objects intact.

    Predicate targets travel on to compile_predicate, which reports the
    originating file and line when a comparison fails to parse. Flattening them
    to bare strings here is what threw that position away.
    """
    return [data] if is_text(data) else list(data)


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
        except StopIteration as e:
            raise exceptions.MissingBaggageError("No baggage found after rule: %r" % (last_rule,)) from e
        else:
            key_name = get_text(rule[0])

            if key_name == "when":
                common_predicates.extend(get_list_of_sources(rule[1]))
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

    # The file's top-level `when:` predicates are compiled and sorted once, then shared by reference
    # with every rule that adds none of its own (parsing them per rule made load cost K x M).
    common_predicates = compile_ruleset(environment, "", "", preamble["common_predicates"])

    for rule_name, data in preamble["rulesets"]:
        if is_when(data[0]):
            concept = "Situation"
            ruleset_predicates = get_list_of_sources(get_next(data[0].values()))
            baggage_data = data[1:]
        elif len(data) > 1 and is_when(data[1]):
            concept = data[0]
            ruleset_predicates = get_list_of_sources(get_next(data[1].values()))
            baggage_data = data[2:]
        elif is_text(data[0]) and concepts.is_registered(get_text(data[0])):
            concept = data[0]
            ruleset_predicates = []
            baggage_data = data[1:]
        else:
            concept = "Situation"
            ruleset_predicates = []
            baggage_data = data[:]

        rule_name = prefix + get_text(rule_name)
        concept = get_text(concept)

        own_predicates = compile_ruleset(environment, concept, rule_name, ruleset_predicates)
        # Merging two sorted runs equals sorting their concatenation, common predicates first on ties.
        predicates = list(heapq.merge(common_predicates, own_predicates)) if own_predicates else common_predicates

        rules[concept]["rules"].append(types.Rule(rule_name, predicates))
        rules[concept]["locations"].update(concepts.compile_baggage(environment, concept, rule_name, baggage_data))

    for ruleset in rules.values():
        ruleset["rules"].sort()

    return {
        "rulebook": dict(rules),
        "includes": preamble["includes"],
        "givens": preamble["givens"],
        "metadata": preamble["metadata"],
    }
