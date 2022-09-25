import logging
import random

logger = logging.getLogger("ravel.query")


def query_predicates(query, predicates):
    matches = []
    qkeys = set()
    qvalue = None
    for predicate in predicates:
        rkey = predicate.name
        predicate = predicate.predicate
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
                matched = predicate(qvalue)
                matches.append(bool(matched))
                if matched:
                    logger.debug(
                        "Matched rule for `%s %r`: %s", rkey, predicate, qvalue
                    )
                break
        else:
            assert rkey not in qkeys
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
    q = sorted(q)
    for rule in rules["rules"]:
        logger.debug("Against rule %r", rule)
        if query_predicates(q, rule.predicates):
            logger.debug("Rule %s accepted", rule.name)
            yield (len(rule.predicates), rule.name, query_by_name(rule.name, rules))
        else:
            logger.debug("Rule %s rejected", rule.name)


def query(concept, q, rules, how_many=None):
    accepted_rules = sorted(
        query_ruleset(q, rules.get(concept, [])),
        reverse=True,
    )
    for score, rname, result in accepted_rules[:how_many]:
        logger.debug(
            "Query result: (rule %s with score of %s) %r", rname, score, result
        )
        yield rname, result


def query_top(concept, q, rules):
    for rname, result in query(concept, q, rules=rules, how_many=1):
        return rname, result


def query_by_name(rname, rules):
    return rules["locations"][rname]
