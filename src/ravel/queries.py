from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: nocover
    from ravel.types import Concept, Predicate, Rulebook, SourceStr

logger = logging.getLogger("ravel.query")


def query_predicates(query: Sequence[Tuple[SourceStr, SourceStr]], predicates: Sequence[Predicate]) -> bool:
    matches = []
    qkeys = set()
    qvalue = None
    for predicate in predicates:
        rkey = predicate.name
        comparison = predicate.comparison
        for qkey, qvalue in query:
            if qkey == rkey:
                qkeys.add(qkey)
                logger.debug(
                    "Checking query `%s: %s` against `%s: %r`",
                    qkey,
                    qvalue,
                    rkey,
                    predicate,
                )
                matched = comparison(qvalue)
                matches.append(bool(matched))
                if matched:
                    logger.debug("Matched rule for `%s %r`: %s", rkey, predicate, qvalue)
                break
        else:
            assert rkey not in qkeys
            try:
                matched = comparison(0)
            except TypeError:
                matched = False
            if matched:
                logger.debug("Matched rule for `%s %r`: %s", rkey, predicate, qvalue)
                matches.append(True)
            else:
                logger.debug("Could not match rule for `%s %r`", rkey, predicate)
                matches.append(False)
                break

    return all(matches)


def query_ruleset(concept: Concept, q):
    q = sorted(q)
    for rule in concept.rules:
        logger.debug("Against rule %r", rule)
        if query_predicates(q, rule.predicates):
            logger.debug("Rule %s accepted", rule.name)
            yield (len(rule.predicates), rule.name, query_concept_by_name(concept, rule.name))
        else:
            logger.debug("Rule %s rejected", rule.name)


def query(rulebook: Rulebook, name, q, how_many=None):
    accepted_rules = sorted(
        query_ruleset(rulebook.concepts.get(name, []), q),
        reverse=True,
    )
    for score, rname, result in accepted_rules[:how_many]:
        logger.debug("Query result: (rule %s with score of %s) %r", rname, score, result)
        yield rname, result


def query_top(rulebook: Rulebook, name: str, q):
    for rname, result in query(rulebook, name, q, how_many=1):
        return rname, result


def query_concept_by_name(concept: Concept, rule_name: str):
    return concept.locations[rule_name]


def query_by_name(rulebook: Rulebook, concept_name: str, rname: str):
    return query_concept_by_name(rulebook.concepts[concept_name], rname)
