from unittest import TestCase
from ensure import ensure

from ravel import predicates
from ravel import types


def source(text):
    return types.Source(0, 0, text)


class TestCompileRuleset(TestCase):
    def test_it_should_compile_predicates_in_a_list_ruleset(self):
        result = predicates.compile_ruleset(
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


class TestGetPredicate(TestCase):
    def test_it_should_produce_a_predicate_function_for_exact_match_with_integer(self):
        predicate = predicates.get_predicate(source('"foo" == 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', 9))))

    def test_it_should_produce_a_predicate_function_for_exact_match_with_float(self):
        predicate = predicates.get_predicate(source('"foo" == 9.0'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', 9.0))))

    def test_it_should_produce_a_predicate_function_for_exact_match_with_string(self):
        predicate = predicates.get_predicate(source('''"foo" == '"foo"' '''))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', '"foo"'))))

    def test_it_should_produce_a_predicate_function_for_greater_than_comparison(self):
        predicate = predicates.get_predicate(source('"foo" > 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '>', 9))))

    def test_it_should_produce_a_predicate_function_for_greater_than_or_equal_to_comparison(self):
        predicate = predicates.get_predicate(source('"foo" >= 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '>=', 9))))

    def test_it_should_produce_a_predicate_function_for_less_than_or_equal_to_comparison(self):
        predicate = predicates.get_predicate(source('"foo" <= 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '<=', 9))))

    def test_it_should_produce_a_predicate_function_for_less_than_comparison(self):
        predicate = predicates.get_predicate(source('"foo" < 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '<', 9))))

    def test_it_should_produce_a_predicate_function_for_inequality(self):
        predicate = predicates.get_predicate(source('"foo" != 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '!=', 9))))
