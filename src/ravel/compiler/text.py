from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from pyrsistent import pmap

from ravel import parsers
from ravel.utils.strings import get_text

if TYPE_CHECKING:  # pragma: nocover
    from ravel.environment import Environment
    from ravel.types import Predicate, SourceStr, Text


def compile_text(
    environment: Environment, concept: str, parent_rule: Any, raw_directive: SourceStr
) -> Union[Text, Predicate]:
    text = get_text(raw_directive).replace("\n", " ")
    return parsers.PlainTextParser().parse(text), pmap()
