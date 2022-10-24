from __future__ import annotations

from typing import TYPE_CHECKING

from ravel import exceptions, parsers, types
from ravel.utils.strings import get_text

if TYPE_CHECKING:  # pragma: nocover
    from ravel.environment import Environment
    from ravel.types import SourceStr


def compile_predicate(environment: Environment, target: SourceStr) -> types.Predicate:
    try:
        comparison = parsers.ComparisonParser().parse(get_text(target))
    except (
        exceptions.ParseError,
        exceptions.ParsimoniousParseError,
        exceptions.VisitationError,
    ):
        exceptions.raise_parse_error(target, exceptions.ComparisonParseError)
    return types.Predicate(name=comparison.quality, comparison=comparison)
