# -*- coding: utf-8 -*-
from unittest import TestCase
from ensure import ensure

from ravel.expressions import Expression, VALUE
from ravel.operations import Operation
from ravel import effects
from ravel import types


class TestCompileEffect(TestCase):
    def test_it_should_compile_an_effect(self):
        effect = effects.compile_effect(
            'Situation', 'test',
            'Quality += 1'
        )
        (ensure(effect)
         .equals(Operation('Quality', '+=', 1, None)))

    def test_it_should_parse_an_effect_with_complex_expression(self):
        effect = effects.compile_effect(
            'Situation', 'test',
            'Quality += value * 2'
        )
        (ensure(effect)
         .equals(
             Operation(
                 'Quality', '+=',
                 Expression(VALUE, '*', 2),
                 None,
             )))


class TestCompileEffects(TestCase):
    def test_it_should_compile_effects(self):
        effect = effects.compile_effects(
            'Situation', 'test',
            [
                'Quality += 1',
                '"Other Quality" += 5'
            ]
        )
        (ensure(effect)
         .equals([
             Operation('Quality', '+=', 1, None),
             Operation('Other Quality', '+=', 5, None),
         ]))
