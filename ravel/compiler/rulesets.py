from .predicates import compile_predicate


def compile_ruleset(concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates.
    """
    return sorted(
        compile_predicate(target)
        for target in ruleset
    )
