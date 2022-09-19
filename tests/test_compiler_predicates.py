import pytest

from ravel import environments
from ravel import exceptions
from ravel import types

from ravel.compiler.predicates import compile_predicate

from .helpers import source


class TestCompilePredicate:
    def test_it_should_produce_a_predicate_function_for_exact_match_with_integer(self, env):
        predicate = compile_predicate(env, source('"foo" == 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '==', 9))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_exact_match_with_float(self, env):
        predicate = compile_predicate(env, source('"foo" == 9.0'))
        expected = types.Predicate('foo', types.Comparison('foo', '==', 9.0))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_exact_match_with_string(self, env):
        predicate = compile_predicate(env, source('''"foo" == '"foo"' '''))
        expected = types.Predicate('foo', types.Comparison('foo', '==', '"foo"'))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_greater_than_comparison(self, env):
        predicate = compile_predicate(env, source('"foo" > 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '>', 9))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_greater_than_or_equal_to_comparison(self, env):
        predicate = compile_predicate(env, source('"foo" >= 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '>=', 9))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_less_than_or_equal_to_comparison(self, env):
        predicate = compile_predicate(env, source('"foo" <= 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '<=', 9))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_less_than_comparison(self, env):
        predicate = compile_predicate(env, source('"foo" < 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '<', 9))
        assert predicate == expected

    def test_it_should_produce_a_predicate_function_for_inequality(self, env):
        predicate = compile_predicate(env, source('"foo" != 9'))
        expected = types.Predicate('foo', types.Comparison('foo', '!=', 9))
        assert predicate == expected

    def test_it_should_raise_on_bad_syntax(self, env):
        with pytest.raises(exceptions.ComparisonParseError):
            compile_predicate(env, source('"foo" !='))
