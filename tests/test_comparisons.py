import itertools as it

import pytest

from ravel import parsers, types


class TestComparison:
    def test_it_should_evaluate_a_gte_comparison(self):
        comp = types.Comparison("Man of Honor", ">=", 3)
        assert comp(4) is True
        assert comp(3) is True
        assert comp(0) is False

    def test_it_should_evaluate_a_gt_comparison(self):
        comp = types.Comparison("Man of Honor", ">", 3)
        assert comp(4) is True
        assert comp(3) is False
        assert comp(0) is False

    def test_it_should_evaluate_an_eq_comparison(self):
        comp = types.Comparison("Man of Honor", "==", 3)
        assert comp(4) is False
        assert comp(3) is True
        assert comp(0) is False

    def test_it_should_evaluate_a_lte_comparison(self):
        comp = types.Comparison("Man of Honor", "<=", 3)
        assert comp(4) is False
        assert comp(3) is True
        assert comp(0) is True

    def test_it_should_evaluate_a_lt_comparison(self):
        comp = types.Comparison("Man of Honor", "<", 3)
        assert comp(4) is False
        assert comp(3) is False
        assert comp(0) is True


class TestComparisonParser:
    @pytest.fixture
    def parser(self):
        return parsers.ComparisonParser()

    @pytest.fixture
    def factors(self):
        comparisons = ("<", "<=", ">", ">=", "==", "!=")
        values = (3, 3.0, 5, 5.0)
        return it.product(comparisons, values)

    def setUp(self):
        self.parser = parsers.ComparisonParser()
        self.comparisons = ("<", "<=", ">", ">=", "==", "!=")
        self.values = (3, 3.0, 5, 5.0)
        self.quote_styles = ('"', "'", "`", '"""', "'''", "```")

    comparisons = ("<", "<=", ">", ">=", "==", "!=")
    values = (3, 3.0, 5, 5.0)

    @pytest.mark.parametrize("comp,value", list(it.product(comparisons, values)))
    def test_it_should_parse_a_simple_quality_name(self, parser, comp, value):
        statement = '"Man of Honor" %s %s' % (comp, value)
        print(statement)
        expected = types.Comparison("Man of Honor", comp, value)
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected

    @pytest.mark.parametrize("comp,value", list(it.product(comparisons, values)))
    def test_it_should_parse_a_comparison(self, parser, comp, value):
        statement = '"Man of Honor" %s %s' % (comp, value)
        print(statement)
        expected = types.Comparison("Man of Honor", comp, value)
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected

    def test_it_should_handle_a_simple_expression(self, parser):
        statement = '"Man of Honor" > 3 * 2'
        print(statement)
        expected = types.Comparison("Man of Honor", ">", types.Expression(3, "*", 2))
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected

    def test_it_should_handle_a_more_complicated_expressions(self, parser):
        statement = '"Man of Honor" > 3 + 2 + 3'
        print(statement)
        expected = types.Comparison(
            "Man of Honor",
            ">",
            types.Expression(3, "+", types.Expression(2, "+", 3)),
        )
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected

    def test_it_should_handle_a_complex_expression(self, parser):
        statement = '"Man of Honor" > 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = types.Comparison(
            "Man of Honor",
            ">",
            types.Expression(
                3,
                "+",
                types.Expression(5, "*", types.Expression(2, "/", types.Expression(3, "-", 2))),
            ),
        )
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected

    def test_it_should_handle_a_simple_expression_with_a_value(self, parser):
        statement = '"Man of Honor" > 3 * value'
        print(statement)
        expected = types.Comparison("Man of Honor", ">", types.Expression(3, "*", types.VALUE))
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Comparison)
        assert result == expected
