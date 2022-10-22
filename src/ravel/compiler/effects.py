from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from pyrsistent import pmap, pvector

from ravel import parsers
from ravel.utils.strings import get_text

from . import logger

if TYPE_CHECKING:  # pragma: nocover
    from pyrsistent import PVector, PMap
    from ravel.environment import Environment
    from ravel.types import Operation


def compile_effect(environment: Environment, concept: str, parent_rule: str, effect: str) -> Tuple[Operation, PMap]:
    logger.debug("Compiling effect for %s:%s:\n%r", concept, parent_rule, effect)
    return parsers.OperationParser().parse(get_text(effect)), pmap()


def compile_effects(environment: Environment, concept: str, parent_rule: str, raw_effects: str) -> PVector:
    return pvector([compile_effect(environment, concept, parent_rule, effect) for effect in raw_effects])
