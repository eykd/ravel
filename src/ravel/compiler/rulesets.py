from __future__ import annotations

from typing import TYPE_CHECKING, List

from . import predicates

if TYPE_CHECKING:  # pragma: nocover
    from collections.abc import Iterable

    from ravel.environments import Environment
    from ravel.types import Predicate, SourceStr


def compile_ruleset(
    environment: Environment, concept_name: str, rule_name: str, ruleset: Iterable[SourceStr]
) -> List[Predicate]:
    """Compile a ruleset declaration into a sorted list of Predicates."""
    return sorted(predicates.compile_predicate(environment, target) for target in ruleset)
