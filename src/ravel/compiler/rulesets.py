from . import predicates


def compile_ruleset(environment, concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates."""
    return sorted(
        predicates.compile_predicate(environment, target) for target in ruleset
    )
