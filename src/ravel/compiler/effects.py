# -*- coding: utf-8 -*-
from ravel import parsers
from ravel.utils.strings import get_text

from . import logger


def compile_effect(environment, concept, parent_rule, effect):
    logger.debug('Compiling effect for %s:%s:\n%r', concept, parent_rule, effect)
    return parsers.OperationParser().parse(get_text(effect)), {}


def compile_effects(environment, concept, parent_rule, raw_effects):
    return [
        compile_effect(environment, concept, parent_rule, effect)
        for effect in raw_effects
    ]
