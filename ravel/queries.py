import collections
import logging
import random

logger = logging.getLogger('ravel.query')


def query_predicates(query, predicates):
    matches = []
    qkeys = set()
    qvalue = None
    for rkey, predicate in predicates:
        for qkey, qvalue in query:
            if qkey == rkey:
                qkeys.add(qkey)
                logger.debug("Checking query `%s: %s` against `%s: %r`", qkey, qvalue, rkey, predicate)
                matched = predicate(qvalue)
                matches.append(bool(matched))
                if matched:
                    logger.debug("Matched rule for `%s %r`: %s", rkey, predicate, qvalue)
                break
        else:
            if rkey not in qkeys:
                try:
                    matched = predicate(0)
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


def query_ruleset(q, rules):
    if isinstance(q, collections.Mapping):
        q = q.items()
    q = sorted(q)
    for rname, predicates, results in rules:
        logger.debug("Against rule %s: %r", rname, predicates)
        if query_predicates(q, predicates):
            logger.debug("Rule %s accepted", rname)
            yield (len(predicates), random.random(), rname, results)
        else:
            logger.debug("Rule %s rejected", rname)


def query(concept, q, rules, how_many=None):
    accepted_rules = sorted(
        query_ruleset(q, rules.get(concept, [])),
        reverse=True,
    )
    for score, rfactor, rname, result in accepted_rules[:how_many]:
        logger.debug("Query result: (rule %s with score of %s) %r", rname, score, result)
        yield result


def query_top(concept, q, rules):
    for result in query(concept, q, rules=rules, how_many=1):
        return result
