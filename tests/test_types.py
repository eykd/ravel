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


class TestStringArithmeticIsRejected:
    @pytest.mark.parametrize("operator", ["*", "%", "-", "/", "//"])
    def test_expression_should_reject_string_operands(self, operator):
        for left, right in [("ab", 3), (3, "ab"), ("ab", "cd")]:
            with pytest.raises(exceptions.EvaluationError):
                types.Expression(left, operator, right).evaluate()

    def test_expression_should_still_concatenate_strings(self):
        assert types.Expression("ab", "+", "cd").evaluate() == "abcd"

    @pytest.mark.parametrize("operator", ["*=", "%=", "-=", "/=", "//="])
    def test_operation_should_reject_a_string_quality(self, operator):
        with pytest.raises(exceptions.EvaluationError):
            types.Operation("X", operator, 2).evaluate("ab")

    def test_operation_should_reject_a_string_operand(self):
        with pytest.raises(exceptions.EvaluationError):
            types.Operation("X", "*=", "ab").evaluate(3)

    def test_operation_should_still_concatenate_and_assign_strings(self):
        assert types.Operation("X", "+=", "cd").evaluate("ab") == "abcd"
        assert types.Operation("X", "=", "cd").evaluate("ab") == "cd"

    def test_a_predicate_with_string_repetition_should_be_false(self):
        comparison = types.Comparison("X", "==", types.Expression("ab", "*", 3))
        assert comparison("abababab") is False
        assert comparison.check(_Lookup()) is False


class _Lookup:
    def get(self, name, /):
        return "ababab"


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


class TestOperationConstraint:
    def test_min_constraint_clamps_a_subtraction(self):
        operation = types.Operation("X", "-=", 10, types.Constraint("min", 0))
        assert operation.evaluate(5) == 0

    def test_max_constraint_clamps_an_addition(self):
        operation = types.Operation("X", "+=", 10, types.Constraint("max", 8))
        assert operation.evaluate(5) == 8

    def test_max_constraint_leaves_a_result_under_the_bound_alone(self):
        operation = types.Operation("X", "+=", 1, types.Constraint("max", 8))
        assert operation.evaluate(5) == 6

    def test_max_constraint_clamps_an_assignment(self):
        operation = types.Operation("X", "=", 20, types.Constraint("max", 8))
        assert operation.evaluate(5) == 8

    def test_constraint_on_a_string_result_raises_constraint_error(self):
        operation = types.Operation("X", "=", types.QualityRef("Name"), types.Constraint("max", 3))
        with pytest.raises(exceptions.ConstraintError):
            operation.evaluate(None, qualities={"Name": "Hi"})


class TestConstraintApply:
    def test_min_raises_low_values_to_the_bound(self):
        assert types.Constraint("min", 0).apply(-5) == 0

    def test_max_lowers_high_values_to_the_bound(self):
        assert types.Constraint("max", 8).apply(15) == 8

    def test_max_leaves_values_under_the_bound_alone(self):
        assert types.Constraint("max", 8).apply(6) == 6

    def test_bound_kind_wins_when_the_bound_is_used(self):
        result = types.Constraint("min", 0.0).apply(-5)
        assert result == 0.0
        assert type(result) is float

    def test_float_result_is_kept_when_within_bound(self):
        result = types.Constraint("min", 0).apply(3.5)
        assert result == 3.5
        assert type(result) is float

    def test_it_should_reject_a_string_result(self):
        with pytest.raises(exceptions.ConstraintError):
            types.Constraint("max", 3).apply("Hi")

    def test_constraint_error_is_an_evaluation_error(self):
        assert issubclass(exceptions.ConstraintError, exceptions.EvaluationError)


class TestStringConcatenationCap:
    def test_it_concatenates_short_strings(self):
        assert types.Expression("a", "+", "b").evaluate() == "ab"
        assert types.Operation("s", "+=", "b").evaluate("a") == "ab"

    def test_it_leaves_numeric_addition_unchanged(self):
        assert types.Expression(2, "+", 3).evaluate() == 5

    def test_it_concatenates_up_to_the_cap(self):
        half = "x" * (types.MAX_STRING_LENGTH // 2)
        assert len(types.Expression(half, "+", half).evaluate()) == types.MAX_STRING_LENGTH
        assert len(types.Operation("s", "+=", half).evaluate(half)) == types.MAX_STRING_LENGTH

    def test_it_rejects_an_expression_over_the_cap(self):
        with pytest.raises(exceptions.EvaluationError, match="maximum string length"):
            types.Expression("x" * types.MAX_STRING_LENGTH, "+", "y").evaluate()

    def test_it_rejects_an_operation_over_the_cap(self):
        with pytest.raises(exceptions.EvaluationError, match="maximum string length"):
            types.Operation("s", "+=", "y").evaluate("x" * types.MAX_STRING_LENGTH)

    def test_an_over_cap_concatenation_makes_a_comparison_false(self):
        overflow = types.Expression("x" * types.MAX_STRING_LENGTH, "+", "y")
        assert types.Comparison("S", "==", overflow)("z") is False

    def test_it_does_not_build_the_oversize_string(self):
        big = "x" * types.MAX_STRING_LENGTH

        # A str subclass whose __add__ would flag any concatenation actually being attempted.
        class Trap(str):
            def __add__(self, other):
                raise AssertionError("concatenated before checking the cap")

        with pytest.raises(exceptions.EvaluationError):
            types.Expression(Trap(big), "+", "y").evaluate()
