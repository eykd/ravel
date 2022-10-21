from __future__ import annotations
from typing import Callable, TYPE_CHECKING, List, Union
from pyrsistent import pmap, pvector
from ravel.utils.strings import get_text

if TYPE_CHECKING:
    from pyrsistent import PMap
    from syml.types import Source
    from ravel.environments import Environment

_HANDLERS = {}


def handler(concept: str) -> Callable:
    """Decorator for concept handlers.

    Usage:

        @baggage.handler('MyConcept')
        def handle_myconcept(concept, rule_name, baggage):
            return "something else based on the baggage!"
    """

    def register_handler(func):
        _HANDLERS[concept] = func
        return func

    return register_handler


def _dummy_handler(environment: Environment, concept: str, rule_name: str, baggage: List[Union[str, Source]]) -> PMap:
    """Return the baggage as-is."""
    return pmap({rule_name: pvector([get_text(b) for b in baggage])})


def get_handler_for(concept: str) -> Callable:
    """Return a handler for the given concept."""
    return _HANDLERS.get(concept, _dummy_handler)


def compile_baggage(environment: Environment, concept: str, rule_name: str, baggage_data: List[Union[str, Source]]):
    """Compile the given baggage using a registered concept handler."""
    return get_handler_for(concept)(environment, concept, rule_name, baggage_data)
