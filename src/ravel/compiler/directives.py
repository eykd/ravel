import itertools as it
from collections.abc import Mapping, Sequence
from typing import Final

from slugify import slugify

from ravel import exceptions, parsers, types
from ravel.utils.data import merge_dicts
from ravel.utils.strings import get_text, is_text, unwrap

from . import effects, logger, text

# Real stories nest choice blocks only a few levels deep. This limit is generous headroom above
# that, chosen to sit comfortably below the depth at which the mutual recursion between
# compile_choice / _compile_directive_bodies / compile_directive would exhaust the interpreter's
# call stack and raise an untyped RecursionError instead of a typed ParseError.
MAX_CHOICE_NESTING_DEPTH: Final = 200


def compile_directives(environment, concept, parent_rule, raw_directives):
    intro, *the_rest = raw_directives
    intro, first_text = parsers.IntroTextParser().parse(unwrap(get_text(intro)))
    directives, subsituations = _compile_directive_bodies(environment, concept, parent_rule, first_text, the_rest)
    return intro, directives, subsituations


def _compile_directive_bodies(environment, concept, parent_rule, first_text, the_rest, depth=0):
    """Compile a situation's (or choice's) directive list, given its own already-namespaced rule."""
    directives = []
    subsituations = []
    if the_rest:
        last_directive = None
        for item in the_rest:
            for directive, situations in compile_directive(environment, concept, parent_rule, item, depth=depth):
                if not isinstance(last_directive, types.Choice) and isinstance(directive, types.Choice):
                    directives.append(types.BeginChoices())
                if isinstance(last_directive, types.Choice) and not isinstance(directive, types.Choice):
                    directives.append(types.GetChoice())
                directives.append(directive)
                subsituations.append(situations)
                last_directive = directive
        if isinstance(last_directive, types.Choice):
            directives.append(types.GetChoice())
    return list(it.chain([first_text], directives)), subsituations


def compile_directive(environment, concept, parent_rule, raw_directive, depth=0):
    if isinstance(raw_directive, Mapping):
        if len(raw_directive) != 1:
            raise exceptions.ParseError("Too many directives in %s" % exceptions.bounded_repr(raw_directive))
        key, directive = list(raw_directive.items())[0]
        if get_text(key) == "choice":
            return [compile_choice(environment, concept, parent_rule, directive, depth=depth)]
        elif get_text(key) == "text":
            return [text.compile_text(environment, concept, parent_rule, directive)]
        elif get_text(key) == "effect":
            if is_text(directive):
                return [effects.compile_effect(environment, concept, parent_rule, directive)]
            elif isinstance(directive, Sequence):
                return effects.compile_effects(environment, concept, parent_rule, directive)
            else:
                raise exceptions.ParseError("Unrecognized effect type: %s" % exceptions.bounded_repr(directive))
        elif get_text(key) == "end":
            return [compile_end(environment, concept, parent_rule, directive)]
        else:
            raise exceptions.ParseError(
                "Unknown directive %s in %s"
                % (exceptions.printable(get_text(key)), exceptions.bounded_repr(raw_directive))
            )
    else:
        return [text.compile_text(environment, concept, parent_rule, raw_directive)]


def compile_end(environment, concept, parent_rule, directive):
    if not is_text(directive):
        raise exceptions.ParseError(
            "end takes an inline outcome label, not a block: %s" % exceptions.bounded_repr(directive)
        )
    return types.End(get_text(directive).strip()), {}


def compile_choice(environment, concept, parent_rule, directives, depth=0):
    if depth > MAX_CHOICE_NESTING_DEPTH:
        raise exceptions.ParseError(
            "Choice nesting exceeds the maximum supported depth (%d) at %s"
            % (MAX_CHOICE_NESTING_DEPTH, exceptions.bounded_repr(parent_rule))
        )
    logger.debug("Compiling choice for %s:%s:\n%r", concept, parent_rule, directives)
    if is_text(directives):
        directives = [directives]
    intro_source, *the_rest = directives
    intro, first_text = parsers.IntroTextParser().parse(unwrap(get_text(intro_source)))
    subrule = environment.location_separator.join([parent_rule, slugify(get_text(intro), allow_unicode=True)])
    # Compile this choice's own body namespaced under its own subrule, not the grandparent's rule,
    # so a choice nested inside this choice's body is addressable as subrule::its-own-slug.
    directives, subsituations = _compile_directive_bodies(
        environment, concept, subrule, first_text, the_rest, depth=depth + 1
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
        raise exceptions.ParseError("%s: %s" % (e.__class__.__name__, exceptions.printable(e.args[0]))) from e
