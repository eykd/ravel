from __future__ import annotations
from typing import TYPE_CHECKING, Tuple
from collections.abc import Sequence, Mapping
import logging

if TYPE_CHECKING:
    from ravel.types import Concept, Predicate, SourceStr, Rulebook

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


def query_ruleset(q, concept: Concept):
    q = sorted(q)
    for rule in concept.rules:
        logger.debug("Against rule %r", rule)
        if query_predicates(q, rule.predicates):
            logger.debug("Rule %s accepted", rule.name)
            yield (len(rule.predicates), rule.name, query_by_name(rule.name, concept))
        else:
            logger.debug("Rule %s rejected", rule.name)


def query(name, q, rulebook: Rulebook, how_many=None):
    accepted_rules = sorted(
        query_ruleset(q, rulebook.concepts.get(name, [])),
        reverse=True,
    )
    for score, rname, result in accepted_rules[:how_many]:
        logger.debug("Query result: (rule %s with score of %s) %r", rname, score, result)
        yield rname, result


def query_top(name, q, rulebook: Rulebook):
    for rname, result in query(name, q, rulebook=rulebook, how_many=1):
        return rname, result


def query_by_name(rname, concept: Concept):
    return concept.locations[rname]
