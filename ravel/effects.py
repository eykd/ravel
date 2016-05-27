# -*- coding: utf-8 -*-
from copy import deepcopy
from functools import wraps
import logging

from .operations import OperationParser

logger = logging.getLogger('effects')


def compile_effect(concept, parent_rule, effect):
    logger.debug('Compiling effect for %s:%s:\n%r', concept, parent_rule, effect)
    return OperationParser().parse(effect)


def compile_effects(concept, parent_rule, raw_effects):
    return [
        compile_effect(concept, parent_rule, effect)
        for effect in raw_effects
    ]
