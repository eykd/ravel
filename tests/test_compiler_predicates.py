from unittest import TestCase

from ravel import environments
from ravel import exceptions
from ravel import types

from ravel.compiler.predicates import compile_predicate

from .helpers import source, ensure


class TestCompilePredicate(TestCase):
    def setUp(self):
        self.env = environments.Environment()

    def test_it_should_produce_a_predicate_function_for_exact_match_with_integer(self):
        predicate = compile_predicate(self.env, source('"foo" == 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', 9))))

    def test_it_should_produce_a_predicate_function_for_exact_match_with_float(self):
        predicate = compile_predicate(self.env, source('"foo" == 9.0'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', 9.0))))

    def test_it_should_produce_a_predicate_function_for_exact_match_with_string(self):
        predicate = compile_predicate(self.env, source('''"foo" == '"foo"' '''))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '==', '"foo"'))))

    def test_it_should_produce_a_predicate_function_for_greater_than_comparison(self):
        predicate = compile_predicate(self.env, source('"foo" > 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '>', 9))))

    def test_it_should_produce_a_predicate_function_for_greater_than_or_equal_to_comparison(self):
        predicate = compile_predicate(self.env, source('"foo" >= 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '>=', 9))))

    def test_it_should_produce_a_predicate_function_for_less_than_or_equal_to_comparison(self):
        predicate = compile_predicate(self.env, source('"foo" <= 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '<=', 9))))

    def test_it_should_produce_a_predicate_function_for_less_than_comparison(self):
        predicate = compile_predicate(self.env, source('"foo" < 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '<', 9))))

    def test_it_should_produce_a_predicate_function_for_inequality(self):
        predicate = compile_predicate(self.env, source('"foo" != 9'))
        (ensure(predicate)
         .equals(types.Predicate('foo', types.Comparison('foo', '!=', 9))))

    def test_it_should_raise_on_bad_syntax(self):
        (ensure(compile_predicate)
         .called_with(self.env, source('"foo" !='))
         .raises(exceptions.ComparisonParseError))
