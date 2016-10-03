from ravel import parsers
from ravel import types

from ravel.utils.data import merge_dicts

from . import concepts
from . import logger

from . import directives as _directives


@concepts.handler('Situation')
def compile_situation_baggage(concept, parent_rule, baggage):
    logger.debug('Compiling situation baggage for %s:%s:\n%r', concept, parent_rule, baggage)

    intro, directives, subsituations = _directives.compile_directives(concept, parent_rule, baggage)
    return {
        parent_rule: types.Situation(intro, directives),
        **merge_dicts(*subsituations),
    }
