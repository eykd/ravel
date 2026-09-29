from ravel import types

from . import predicates


def _term_key(term):
    """A total-order key for one comparison operand, whatever its type.

    Numbers sort numerically among themselves (so same-typed orderings are unchanged); other types
    are separated by a fixed tag, never by ``id()`` or hash, so the order is identical across runs.
    """
    if isinstance(term, (int, float)):
        return (0, term, "")
    if isinstance(term, str):
        return (1, 0, term)
    if isinstance(term, types.QualityRef):
        return (2, 0, term.name)
    if isinstance(term, types.Value):
        return (3, 0, "")
    if isinstance(term, types.Expression):
        return (4, 0, (_term_key(term.term1), term.operator, _term_key(term.term2)))
    return (5, 0, repr(term))


def predicate_sort_key(predicate):
    """A total-order sort key for a compiled Predicate: name, comparator, then a type-tagged operand.

    Predicates on one quality and comparator may carry operands of different types (``x > 1`` beside
    ``x > y``), which Python cannot compare directly.
    """
    comparison = predicate.predicate
    return (predicate.name, comparison.quality, comparison.comparator, _term_key(comparison.expression))


def compile_ruleset(environment, concept, rule_name, ruleset):
    """Compile a ruleset declaration into a sorted list of Predicates."""
    return sorted(
        (predicates.compile_predicate(environment, target) for target in ruleset),
        key=predicate_sort_key,
    )
