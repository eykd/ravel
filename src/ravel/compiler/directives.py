from collections.abc import Mapping, Sequence
import itertools as it

from slugify import slugify_unicode

from ravel import exceptions
from ravel import parsers
from ravel import types

from ravel.utils.data import merge_dicts
from ravel.utils.strings import get_text, is_text, unwrap

from . import effects
from . import text

from . import logger


def compile_directives(environment, concept, parent_rule, raw_directives):
    intro, *the_rest = raw_directives
    intro, first_text = parsers.IntroTextParser().parse(unwrap(get_text(intro)))
    directives = []
    subsituations = []
    if the_rest:
        last_directive = None
        for item in the_rest:
            for directive, situations in compile_directive(
                environment, concept, parent_rule, item
            ):
                if not isinstance(last_directive, types.Choice) and isinstance(
                    directive, types.Choice
                ):
                    directives.append(types.BeginChoices())
                if isinstance(last_directive, types.Choice) and not isinstance(
                    directive, types.Choice
                ):
                    directives.append(types.GetChoice())
                directives.append(directive)
                subsituations.append(situations)
                last_directive = directive
        if isinstance(last_directive, types.Choice):
            directives.append(types.GetChoice())
    return intro, list(it.chain([first_text], directives)), subsituations


def compile_directive(environment, concept, parent_rule, raw_directive):
    if isinstance(raw_directive, Mapping):
        if len(raw_directive) != 1:
            raise exceptions.ParseError("Too many directives in %s" % raw_directive)
        key, directive = list(raw_directive.items())[0]
        if get_text(key) == "choice":
            return [compile_choice(environment, concept, parent_rule, directive)]
        elif get_text(key) == "text":
            return [text.compile_text(environment, concept, parent_rule, directive)]
        elif get_text(key) == "effect":
            if is_text(directive):
                return [
                    effects.compile_effect(environment, concept, parent_rule, directive)
                ]
            elif isinstance(directive, Sequence):
                return effects.compile_effects(
                    environment, concept, parent_rule, directive
                )
            else:
                raise exceptions.ParseError("Unrecognized effect type: %r" % directive)
        else:
            raise exceptions.ParseError(
                "Unknown directive %s in %r" % (get_text(key), raw_directive)
            )
    else:
        return [text.compile_text(environment, concept, parent_rule, raw_directive)]


def compile_choice(environment, concept, parent_rule, directives):
    logger.debug("Compiling choice for %s:%s:\n%r", concept, parent_rule, directives)
    if is_text(directives):
        directives = [directives]
    intro, directives, subsituations = compile_directives(
        environment, concept, parent_rule, directives
    )
    subrule = environment.location_separator.join(
        [parent_rule, slugify_unicode(get_text(intro), to_lower=True)]
    )
    try:
        return (
            types.Choice(subrule),
            {
                subrule: types.Situation(intro, directives),
                **merge_dicts(*subsituations),
            },
        )
    except Exception as e:
        raise exceptions.ParseError("%s: %s" % (e.__class__.__name__, e.args[0]))
