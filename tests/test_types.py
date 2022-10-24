import pytest

from ravel import types


class TestText:
    def test_it_should_stringify_nicely(self):
        text = types.Text("Some plain text.")
        assert str(text) == "Some plain text."


class TestComparison:
    def test_it_should_repr_nicely(self):
        comp = types.Comparison(
            quality="Test",
            comparator=">",
            expression=5,
        )
        assert repr(comp) == "('Test' > 5)"

    @pytest.mark.parametrize("cmp, expected", [("=", False), (">=", False), ("<=", True), ("<", True)])
    def test_it_should_perform_a_simple_comparison_on_a_default_value(self, cmp, expected):
        comparison = types.Comparison(
            quality="Foo",
            comparator=cmp,
            expression=2,
        )
        result = comparison.evaluate(None)
        assert result == expected

    @pytest.mark.parametrize("cmp, expected", [("=", False), (">=", False), ("<=", True), ("<", True)])
    def test_it_should_perform_a_complex_comparison_on_a_default_value(self, cmp, expected):
        comparison = types.Comparison(
            quality="Foo",
            comparator=cmp,
            expression=types.Expression(
                term1=5,
                operator="-",
                term2=3,
            ),
        )
        result = comparison.evaluate(None)
        assert result == expected

    @pytest.mark.parametrize("cmp, expected", [("=", True), (">=", True), ("<=", True), ("<", False)])
    def test_it_should_perform_a_simple_comparison_on_an_existing_value(self, cmp, expected):
        comparison = types.Comparison(
            quality="Foo",
            comparator=cmp,
            expression=2,
        )
        result = comparison.evaluate(2)
        assert result == expected

    @pytest.mark.parametrize("cmp, expected", [("=", True), (">=", True), ("<=", True), ("<", False)])
    def test_it_should_perform_a_complex_comparison_on_an_existing_value(self, cmp, expected):
        comparison = types.Comparison(
            quality="Foo",
            comparator=cmp,
            expression=types.Expression(
                term1=5,
                operator="-",
                term2=3,
            ),
        )
        result = comparison.evaluate(2)
        assert result == expected


# class TestEffect:
#     def test_it_should_perform_an_effect(self):
#         effect = types.Effect(

#         )


class TestExpression:
    def test_it_should_evaluate_a_simple_expression(self):
        exp = types.Expression(
            term1=1,
            operator="+",
            term2=1,
        )
        result = exp.evaluate()
        assert result == 2

    def test_it_should_evaluate_a_complex_expression(self):
        exp = types.Expression(
            term1=types.Expression(
                term1=5,
                operator="*",
                term2=5,
            ),
            operator="+",
            term2=types.Expression(
                term1=5,
                operator="*",
                term2=5,
            ),
        )
        result = exp.evaluate()
        assert result == 50


class TestOperation:
    @pytest.mark.parametrize("op, expected", [("=", 2), ("+=", 2), ("-=", -2), ("*=", 0)])
    def test_it_should_perform_a_simple_operation_on_a_default_value(self, op, expected):
        operation = types.Operation(
            quality="Foo",
            operator=op,
            expression=2,
            constraint=None,
        )
        result = operation.evaluate(None)
        assert result == expected

    @pytest.mark.parametrize("op, expected", [("=", 2), ("+=", 2), ("-=", -2), ("*=", 0)])
    def test_it_should_perform_a_complex_operation_on_a_default_value(self, op, expected):
        operation = types.Operation(
            quality="Foo",
            operator=op,
            expression=types.Expression(
                term1=5,
                operator="-",
                term2=3,
            ),
            constraint=None,
        )
        result = operation.evaluate(None)
        assert result == expected

    @pytest.mark.parametrize("op, expected", [("=", 2), ("+=", 4), ("-=", 0), ("*=", 4)])
    def test_it_should_perform_a_simple_operation_on_an_existing_value(self, op, expected):
        operation = types.Operation(
            quality="Foo",
            operator=op,
            expression=2,
            constraint=None,
        )
        result = operation.evaluate(2)
        assert result == expected

    @pytest.mark.parametrize("op, expected", [("=", 2), ("+=", 4), ("-=", 0), ("*=", 4)])
    def test_it_should_perform_a_complex_operation_on_an_existing_value(self, op, expected):
        operation = types.Operation(
            quality="Foo",
            operator=op,
            expression=types.Expression(
                term1=5,
                operator="-",
                term2=3,
            ),
            constraint=None,
        )
        result = operation.evaluate(2)
        assert result == expected
