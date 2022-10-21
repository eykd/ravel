from __future__ import annotations
from typing import TYPE_CHECKING, Union

from ravel import exceptions, parsers, types
from ravel.utils.strings import get_text

if TYPE_CHECKING:
    from syml.types import Source
    from ravel.environment import Environment


def compile_predicate(environment: Environment, target: Union[Source, str]) -> types.Predicate:
    try:
        comparison = parsers.ComparisonParser().parse(get_text(target))
    except (
        exceptions.ParseError,
        exceptions.ParsimoniousParseError,
        exceptions.VisitationError,
    ):
        exceptions.raise_parse_error(target, exceptions.ComparisonParseError)
    return types.Predicate(comparison.quality, comparison)
