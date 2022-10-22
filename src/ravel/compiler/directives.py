from __future__ import annotations

import itertools as it
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Dict

from pyrsistent import pmap, pvector, freeze
from slugify import slugify_unicode  # type: ignore

from ravel import exceptions, parsers, types
from ravel.utils.data import merge_dicts
from ravel.utils.strings import get_text, is_text, unwrap

from . import effects, logger, text

if TYPE_CHECKING:  # pragma: nocover
    from pyrsistent import PVector
    from ravel.environments import Environment


def compile_directives(environment: Environment, concept: str, parent_rule: Any, raw_directives: Dict[str, str]):
    intro, *the_rest = raw_directives
    intro, first_text = parsers.IntroTextParser().parse(unwrap(get_text(intro)))
    directives = []
    subsituations = []
    if the_rest:
        last_directive = None
        for item in the_rest:
            for directive, situations in compile_directive(environment, concept, parent_rule, item):
                if not isinstance(last_directive, types.Choice) and isinstance(directive, types.Choice):
                    directives.append(types.BeginChoices())
                if isinstance(last_directive, types.Choice) and not isinstance(directive, types.Choice):
                    directives.append(types.GetChoice())
                directives.append(directive)
                subsituations.append(situations)
                last_directive = directive
        if isinstance(last_directive, types.Choice):
            directives.append(types.GetChoice())
    return intro, pvector(it.chain([first_text], directives)), subsituations


def compile_directive(
    environment: Environment, concept: str, parent_rule: Any, raw_directive: Dict[str, str]
) -> PVector:
    if isinstance(raw_directive, Mapping):
        if len(raw_directive) != 1:
            raise exceptions.ParseError("Too many directives in %s" % raw_directive)
        key, directive = list(raw_directive.items())[0]
        if get_text(key) == "choice":
            return pvector([compile_choice(environment, concept, parent_rule, directive)])
        elif get_text(key) == "text":
            return pvector([text.compile_text(environment, concept, parent_rule, directive)])
        elif get_text(key) == "effect":
            if is_text(directive):
                return pvector([effects.compile_effect(environment, concept, parent_rule, directive)])
            elif isinstance(directive, Sequence):
                return effects.compile_effects(environment, concept, parent_rule, directive)
            else:
                raise exceptions.ParseError("Unrecognized effect type: %r" % directive)
        else:
            raise exceptions.ParseError("Unknown directive %s in %r" % (get_text(key), raw_directive))
    else:
        return freeze([text.compile_text(environment, concept, parent_rule, raw_directive)])


def compile_choice(environment: Environment, concept: str, parent_rule: Any, directives: str):
    logger.debug("Compiling choice for %s:%s:\n%r", concept, parent_rule, directives)
    if is_text(directives):
        directives = [directives]
    intro, directives, subsituations = compile_directives(environment, concept, parent_rule, directives)
    subrule = environment.loader.location_separator.join([parent_rule, slugify_unicode(get_text(intro), to_lower=True)])

    return (
        types.Choice(subrule),
        freeze(
            {
                subrule: types.Situation(intro, directives),
                **merge_dicts(*subsituations),
            }
        ),
    )
