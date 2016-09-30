from unittest import TestCase

from ravel import types

from ravel.compiler.rulesets import compile_ruleset

from .helpers import source, ensure


class TestCompileRuleset(TestCase):
    def test_it_should_compile_predicates_in_a_list_ruleset(self):
        result = compile_ruleset(
            'test-concept',
            'test-rule',
            [
                source('"foo" == 9'),
                source('bar < 5'),
                source('blah == "boo"'),
            ]
        )

        expected = [
            types.Predicate(
                name = 'bar',
                predicate = types.Comparison(
                    quality = 'bar',
                    comparison = '<',
                    expression = 5
                )
            ),
            types.Predicate(
                name = 'blah',
                predicate = types.Comparison(
                    quality = 'blah',
                    comparison = '==',
                    expression = 'boo'
                )
            ),
            types.Predicate(
                name = 'foo',
                predicate = types.Comparison(
                    quality = 'foo',
                    comparison = '==',
                    expression = 9
                )
            ),
        ]

        ensure(result).equals(expected)
