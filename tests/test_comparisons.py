import itertools as it
from unittest import TestCase
from ensure import ensure

from ravel import parsers
from ravel import types


class TestComparison(TestCase):
    def test_it_should_evaluate_a_gte_comparison(self):
        comp = types.Comparison('Man of Honor', '>=', 3)
        ensure(comp(4)).is_true()
        ensure(comp(3)).is_true()
        ensure(comp(0)).is_false()

    def test_it_should_evaluate_a_gt_comparison(self):
        comp = types.Comparison('Man of Honor', '>', 3)
        ensure(comp(4)).is_true()
        ensure(comp(3)).is_false()
        ensure(comp(0)).is_false()

    def test_it_should_evaluate_an_eq_comparison(self):
        comp = types.Comparison('Man of Honor', '==', 3)
        ensure(comp(4)).is_false()
        ensure(comp(3)).is_true()
        ensure(comp(0)).is_false()

    def test_it_should_evaluate_a_lte_comparison(self):
        comp = types.Comparison('Man of Honor', '<=', 3)
        ensure(comp(4)).is_false()
        ensure(comp(3)).is_true()
        ensure(comp(0)).is_true()

    def test_it_should_evaluate_a_lt_comparison(self):
        comp = types.Comparison('Man of Honor', '<', 3)
        ensure(comp(4)).is_false()
        ensure(comp(3)).is_false()
        ensure(comp(0)).is_true()


class TestComparisonParser(TestCase):
    def setUp(self):
        self.parser = parsers.ComparisonParser()
        self.comparisons = ('<', '<=', '>', '>=', '==', '!=')
        self.values = (3, 3.0, 5, 5.0)
        self.quote_styles = ('"', "'", '`', '"""', "'''", '```')

    def test_it_should_parse_a_simple_quality_name(self):
        factors = it.product(self.comparisons, self.values)
        for comp, val in factors:
            statement = '"Man of Honor" %s %s' % (comp, val)
            print(statement)
            expected = types.Comparison(
                'Man of Honor', comp, val
            )
            result = self.parser.parse(statement)
            print("Got", result)
            print("Exp", expected)
            ensure(result).is_an(types.Comparison)
            ensure(result).equals(expected)

    def test_it_should_parse_a_comparison(self):
        factors = it.product(self.comparisons, self.values)
        for comp, val in factors:
            statement = '"Man of Honor" %s %s' % (comp, val)
            print(statement)
            expected = types.Comparison(
                'Man of Honor', comp, val
            )
            result = self.parser.parse(statement)
            print("Got", result)
            print("Exp", expected)
            ensure(result).is_an(types.Comparison)
            ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression(self):
        statement = '"Man of Honor" > 3 * 2'
        print(statement)
        expected = types.Comparison(
            'Man of Honor', '>', types.Expression(3, '*', 2))
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_more_complicated_expressions(self):
        statement = '"Man of Honor" > 3 + 2 + 3'
        print(statement)
        expected = types.Comparison(
            'Man of Honor', '>',
            types.Expression(
                3, '+',
                types.Expression(2, '+', 3)),
        )
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_complex_expression(self):
        statement = '"Man of Honor" > 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = types.Comparison(
            'Man of Honor', '>',
            types.Expression(
                3, '+',
                types.Expression(
                    5, '*',
                    types.Expression(
                        2, '/',
                        types.Expression(3, '-', 2)
                    )
                )
            ),
        )
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression_with_a_value(self):
        statement = '"Man of Honor" > 3 * value'
        print(statement)
        expected = types.Comparison(
            'Man of Honor', '>', types.Expression(3, '*', types.VALUE))
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_a(types.Comparison)
        ensure(result).equals(expected)
