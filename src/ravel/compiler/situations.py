from ravel import exceptions, types
from ravel.utils.data import merge_dicts

from . import concepts
from . import directives as _directives
from . import logger


@concepts.handler("Situation")
def compile_situation_baggage(environment, concept, parent_rule, baggage):
    logger.debug(
        "Compiling situation baggage for %s:%s:\n%r", concept, parent_rule, baggage
    )

    if not baggage:
        raise exceptions.MissingBaggageError(
            "Missing baggage for {concept}:{parent_rule}"
        )

    intro, directives, subsituations = _directives.compile_directives(
        environment, concept, parent_rule, baggage
    )
    return {
        parent_rule: types.Situation(intro, directives),
        **merge_dicts(*subsituations),
    }
