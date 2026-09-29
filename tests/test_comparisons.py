import itertools as it

import pytest
from parsimonious import Grammar

from ravel import exceptions, grammars, parsers, types


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
            types.Expression(types.Expression(3, "+", 2), "+", 3),
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
                types.Expression(
                    types.Expression(5, "*", 2),
                    "/",
                    types.Expression(3, "-", 2),
                ),
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


class TestComparisonThreadsQualities:
    def test_check_reads_a_quality_ref_from_the_qualities(self):
        comparison = types.Comparison("Health", "<", types.QualityRef("Max"))
        assert comparison.check({"Health": 7, "Max": 10}) is True

    def test_call_binds_value_placeholder_to_the_subject(self):
        comparison = types.Comparison("Health", ">=", types.VALUE)
        assert comparison(7) is True

    def test_check_is_false_when_division_by_zero(self):
        comparison = types.Comparison("X", ">", types.Expression(10, "/", types.QualityRef("Y")))
        assert comparison.check({"X": 2}) is False

    def test_call_is_false_when_division_by_zero(self):
        comparison = types.Comparison("X", ">", types.Expression(10, "/", types.QualityRef("Y")))
        assert comparison(2, qualities={"X": 2}) is False

    def test_check_is_false_when_operands_are_incompatible(self):
        comparison = types.Comparison("X", ">", types.QualityRef("Name"))
        assert comparison.check({"X": 2, "Name": "a"}) is False

    def test_evaluate_raises_evaluation_error_chaining_zero_division(self):
        comparison = types.Comparison("X", ">", types.Expression(10, "/", types.QualityRef("Y")))
        with pytest.raises(exceptions.EvaluationError) as excinfo:
            comparison.evaluate(2, qualities={"X": 2})
        assert isinstance(excinfo.value.__cause__, ZeroDivisionError)

    def test_evaluate_raises_evaluation_error_chaining_type_error(self):
        comparison = types.Comparison("X", ">", types.QualityRef("Name"))
        with pytest.raises(exceptions.EvaluationError) as excinfo:
            comparison.evaluate(2, qualities={"X": 2, "Name": "a"})
        assert isinstance(excinfo.value.__cause__, TypeError)

    def test_check_lets_a_lookup_type_error_propagate_bare(self):
        class ExplodingLookup:
            def get(self, name):
                raise TypeError("broken lookup")

        comparison = types.Comparison("X", ">", 1)
        with pytest.raises(TypeError) as excinfo:
            comparison.check(ExplodingLookup())
        assert not isinstance(excinfo.value, exceptions.EvaluationError)

    def test_predicate_check_forwards_qualities(self):
        predicate = types.Predicate("p", types.Comparison("Health", "<", types.QualityRef("Max")))
        assert predicate.check({"Health": 7, "Max": 10}) is True

    def test_text_check_forwards_qualities(self):
        text = types.Text("hi", predicate=types.Comparison("Health", "<", types.QualityRef("Max")))
        assert text.check({"Health": 7, "Max": 10}) is True


class TestComparisonParserQualityReferences:
    @pytest.fixture
    def parser(self):
        return parsers.ComparisonParser()

    def test_a_quoted_string_on_the_right_stays_a_string(self, parser):
        assert parser.parse('Name == "Wearing Cloak"') == types.Comparison("Name", "==", "Wearing Cloak")

    def test_a_bracketed_name_on_the_right_is_a_quality_reference(self, parser):
        assert parser.parse("X == [Y]") == types.Comparison("X", "==", types.QualityRef("Y"))

    def test_a_quoted_subject_is_kept(self, parser):
        assert parser.parse('"Wearing Cloak" >= 1') == types.Comparison("Wearing Cloak", ">=", 1)

    def test_the_grammar_is_built_from_the_shared_comparison_grammar(self):
        assert str(parsers.ComparisonParser.grammar) == str(Grammar(grammars.comparison_grammar))
