from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from pyrsistent import freeze

from ravel import exceptions, types
from ravel.compiler import concepts
from ravel.compiler import directives as _directives
from ravel.compiler import logger
from ravel.utils.data import merge_dicts

if TYPE_CHECKING:  # pragma: nocover
    from ravel.environments import Environment


@concepts.handler("Situation")
def compile_situation_baggage(environment: Environment, concept: str, parent_rule: Any, baggage: Dict[str, str]):
    logger.debug("Compiling situation baggage for %s:%s:\n%r", concept, parent_rule, baggage)

    if not baggage:
        raise exceptions.MissingBaggageError("Missing baggage for {concept}:{parent_rule}")

    intro, directives, subsituations = _directives.compile_directives(environment, concept, parent_rule, baggage)
    return freeze(
        {
            parent_rule: types.Situation(intro, directives),
            **merge_dicts(*subsituations),
        }
    )
