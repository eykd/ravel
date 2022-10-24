from __future__ import annotations

import itertools as it
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Callable, Dict, List, Union

from funcy import first, second
from pyrsistent import freeze, pmap, pvector

from ravel import exceptions, types
from ravel.compiler import situations  # noqa
from ravel.compiler import concepts, effects
from ravel.compiler.rulesets import compile_ruleset
from ravel.types import Rulebook
from ravel.utils.strings import get_text, is_text

if TYPE_CHECKING:  # pragma: nocover
    from pyrsistent import PMap, PVector
    from syml.types import Source

    from ravel.environments import Environment
    from ravel.types import Effect, Operation, Predicate


def get_next(seq: Iterable) -> Callable:
    return next(iter(seq))


def is_when(data: Mapping) -> bool:
    return isinstance(data, Mapping) and len(data) == 1 and get_text(get_next(data.keys())) == "when"


def get_list_of_texts(data: Union[Sequence, Source, str]) -> PVector:
    return pvector([get_text(data)] if is_text(data) else [get_text(t) for t in data])


def compile_givens(environment: Environment, data: Union[str, Source, Sequence]) -> PVector[Operation]:
    if is_text(data):
        data = pvector([data])
    return pvector([op for op, _ in effects.compile_effects(environment, "", "", data)])


def compile_about(data: Mapping) -> PMap[str, str]:
    return pmap({get_text(key): get_text(value) for key, value in data.items()})


def compile_preamble(environment: Environment, rulebook: Mapping):
    includes: List[str] = []
    givens: List[Effect] = []
    common_predicates: List[str] = []
    metadata: Dict[str, str] = {}

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

    return freeze(
        {
            "includes": includes,
            "givens": givens,
            "common_predicates": common_predicates,
            "metadata": metadata,
            "rulesets": pvector(rulesets),
        }
    )


def compile_rulebook(environment: Environment, rulebook: Dict, prefix: str = "") -> PMap:
    """Compile a rulebook declaration"""
    preamble = compile_preamble(environment, rulebook)

    concept_rules: Dict[str, List] = defaultdict(list)
    concept_locations: Dict[str, List] = defaultdict(dict)

    for rule_name, data in preamble["rulesets"]:
        if is_when(first(data)):
            concept_name = "Situation"
            ruleset_predicates = get_list_of_texts(get_next(data[0].values()))
            baggage_data = data[1:]
        elif is_when(second(data)):
            concept_name = data[0]
            ruleset_predicates = get_list_of_texts(get_next(data[1].values()))
            baggage_data = data[2:]
        else:
            concept_name = "Situation"
            ruleset_predicates = []
            baggage_data = data[:]

        rule_name = prefix + get_text(rule_name)
        concept_name = get_text(concept_name)

        concept_rules[concept_name].append(
            types.Rule(
                rule_name,
                compile_ruleset(
                    environment,
                    concept_name,
                    rule_name,
                    preamble["common_predicates"] + ruleset_predicates,
                ),
            )
        )
        concept_locations[concept_name].update(
            concepts.compile_baggage(environment, concept_name, rule_name, baggage_data)
        )

    for ruleset in concept_rules.values():
        ruleset.sort()

    concepts_rules = {
        concept_name: types.Concept(rules=concept_rules[concept_name], locations=concept_locations[concept_name])
        for concept_name in (set(concept_rules) | set(concept_locations))
    }

    return Rulebook(
        concepts=freeze(concepts_rules),
        includes=freeze(preamble["includes"]),
        givens=freeze(preamble["givens"]),
        metadata=freeze(preamble["metadata"]),
    )


def compile_master_rulebook(rulebooks: List[Rulebook], metadata: Dict[str, str], givens: List[Effect]):
    concept_rules: Dict[str, List[Predicate]] = defaultdict(list)
    concept_locations: Dict[str, Dict] = defaultdict(dict)

    for rulebook in rulebooks:
        for concept, ruleset in rulebook.concepts.items():
            concept_rules[concept].extend(ruleset.rules)
            concept_locations[concept].update(ruleset.locations)

    for ruleset in concept_rules.values():
        ruleset.sort()

    concepts_rules = {
        concept: types.Concept(rules=concept_rules[concept], locations=concept_locations[concept])
        for concept in (set(concept_rules) | set(concept_locations))
    }

    return types.Rulebook(
        metadata=freeze(metadata),
        concepts=freeze(concepts_rules),
        givens=freeze(givens),
    )
