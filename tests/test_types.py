import pytest

from ravel import exceptions, types


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


class TestOperationEvaluationContext:
    def test_it_should_bind_value_to_the_subject_quality(self):
        operation = types.Operation("X", "+=", types.Expression(types.VALUE, "*", 2))
        assert operation.evaluate(10) == 30

    def test_it_should_bind_value_to_zero_for_an_unset_subject(self):
        operation = types.Operation("X", "+=", types.Expression(types.VALUE, "+", 1))
        assert operation.evaluate(None) == 1

    def test_it_should_read_other_qualities(self):
        expression = types.Expression(types.QualityRef("Health"), "+", types.QualityRef("Bonus"))
        operation = types.Operation("X", "=", expression)
        assert operation.evaluate(None, qualities={"Health": 7, "Bonus": 3}) == 10

    def test_it_should_true_divide_to_a_float(self):
        operation = types.Operation("Health", "-=", types.Expression(types.VALUE, "/", 10))
        result = operation.evaluate(50)
        assert result == 45.0
        assert isinstance(result, float)

    def test_it_should_raise_evaluation_error_on_a_type_mismatch(self):
        with pytest.raises(exceptions.EvaluationError) as excinfo:
            types.Operation("X", "+=", 1).evaluate("a")
        assert isinstance(excinfo.value.__cause__, TypeError)

    def test_it_should_not_wrap_a_failing_quality_lookup(self):
        class BadLookup:
            def get(self, name, /):
                raise TypeError("bad lookup")

        operation = types.Operation("X", "=", types.QualityRef("Health"))
        with pytest.raises(TypeError) as excinfo:
            operation.evaluate(None, qualities=BadLookup())
        assert not isinstance(excinfo.value, exceptions.EvaluationError)


class TestPredicate:
    def test_it_should_pass_when_there_is_no_predicate(self):
        assert types.Predicate("Foo", None).check({}) is True

    def test_it_should_delegate_to_its_predicate(self):
        comparison = types.Comparison(quality="Foo", comparator=">", expression=2)
        predicate = types.Predicate("Foo", comparison)

        assert predicate.check({"Foo": 5}) is True
        assert predicate.check({"Foo": 1}) is False


class TestQualityRef:
    def test_it_should_evaluate_to_the_quality_value(self):
        assert types.QualityRef("Health").evaluate(qualities={"Health": 7}) == 7

    def test_it_should_evaluate_to_zero_when_the_quality_is_unset(self):
        assert types.QualityRef("Health").evaluate(qualities={}) == 0


class TestValue:
    def test_it_should_evaluate_to_the_current_qvalue(self):
        assert types.VALUE.evaluate(qvalue=10) == 10

    def test_it_should_be_a_value_instance(self):
        assert isinstance(types.VALUE, types.Value)

    def test_it_should_equal_any_value_instance(self):
        assert types.Value() == types.VALUE


class TestExpressionContextThreading:
    def test_it_should_evaluate_a_quality_ref_term_against_qualities(self):
        exp = types.Expression(types.QualityRef("Health"), "+", 1)
        assert exp.evaluate(qualities={"Health": 7}) == 8

    def test_it_should_evaluate_value_against_qvalue(self):
        assert types.Expression(types.VALUE, "*", 2).evaluate(qvalue=10) == 20

    def test_it_should_pass_the_context_to_nested_expressions(self):
        inner = types.Expression(types.QualityRef("Health"), "*", types.VALUE)
        outer = types.Expression(inner, "+", 1)
        assert outer.evaluate(qualities={"Health": 7}, qvalue=2) == 15

    def test_it_should_still_evaluate_without_context(self):
        assert types.Expression(3, "+", 2).evaluate() == 5


class TestExpressionEvaluationFailures:
    def test_it_should_raise_evaluation_error_on_division_by_zero(self):
        with pytest.raises(exceptions.EvaluationError) as excinfo:
            types.Expression(1, "/", 0).evaluate()
        assert isinstance(excinfo.value.__cause__, ZeroDivisionError)

    def test_it_should_raise_evaluation_error_on_a_type_mismatch(self):
        with pytest.raises(exceptions.EvaluationError) as excinfo:
            types.Expression("a", "+", 1).evaluate()
        assert isinstance(excinfo.value.__cause__, TypeError)

    def test_it_should_not_wrap_a_term_evaluation_failure(self):
        class BadTerm:
            def evaluate(self, **kwargs):
                raise TypeError("bad term")

        with pytest.raises(TypeError) as excinfo:
            types.Expression(BadTerm(), "+", 1).evaluate()
        assert not isinstance(excinfo.value, exceptions.EvaluationError)
