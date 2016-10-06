import itertools as it

from slugify import slugify_unicode

from ravel import exceptions
from ravel import parsers
from ravel import types

from ravel.utils.data import merge_dicts

from .effects import compile_effect
from .text import compile_text

from . import logger


def compile_directives(environment, concept, parent_rule, raw_directives):
    intro, *the_rest = raw_directives
    try:
        intro, first_text = parsers.IntroTextParser().parse(intro.text)
    except AttributeError:
        raise exceptions.ParseError("No intro text found:\n%r" % intro)
    directives = []
    subsituations = []
    if the_rest:
        last_directive = None
        for item in the_rest:
            directive, situations = compile_directive(environment, concept, parent_rule, item)
            if isinstance(last_directive, types.Choice) and not isinstance(directive, types.Choice):
                directives.append(types.GetChoice())
            directives.append(directive)
            subsituations.append(situations)
            last_directive = directive
        if isinstance(last_directive, types.Choice):
            directives.append(types.GetChoice())
    return intro, list(it.chain([first_text], directives)), subsituations


def compile_directive(environment, concept, parent_rule, raw_directive):
    if isinstance(raw_directive, dict):
        if len(raw_directive) != 1:
            raise exceptions.ParseError("Too many directives in %s" % raw_directive)
        key, directive = list(raw_directive.items())[0]
        if key.text == 'choice':
            return compile_choice(environment, concept, parent_rule, directive)
        elif key.text == 'text':
            return compile_text(environment, concept, parent_rule, directive)
        elif key.text == 'effect':
            return compile_effect(environment, concept, parent_rule, directive)
        else:
            raise exceptions.ParseError("Unknown directive %s in %r" % (key.text, raw_directive))
    else:
        return compile_text(environment, concept, parent_rule, raw_directive)


def compile_choice(environment, concept, parent_rule, directives):
    logger.debug('Compiling choice for %s:%s:\n%r', concept, parent_rule, directives)
    if not isinstance(directives, list):
        directives = [directives]
    intro, directives, subsituations = compile_directives(environment, concept, parent_rule, directives)
    subrule = environment.location_separator.join(
        [parent_rule, slugify_unicode(intro.text, to_lower=True)]
    )
    return (
        types.Choice(subrule),
        {subrule: types.Situation(intro, directives), **merge_dicts(*subsituations)}
    )
