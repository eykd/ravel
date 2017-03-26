from unittest import TestCase

from .helpers import ensure

from ravel import types


class TextTests(TestCase):
    def test_it_should_stringify_nicely(self):
        text = types.Text('Some plain text.')
        ensure(str(text)).equals('Some plain text.')


class ComparisonTests(TestCase):
    def test_it_should_repr_nicely(self):
        comp = types.Comparison(
            quality = 'Test',
            comparator = '>',
            expression = 5,
        )
        ensure(repr(comp)).equals("('Test' > 5)")

    def test_it_should_perform_a_simple_comparison_on_a_default_value(self):
        for cmp, expected in [('=', False), ('>=', False), ('<=', True), ('<', True)]:
            comparison = types.Comparison(
                quality = 'Foo',
                comparator = cmp,
                expression = 2,
            )
            result = comparison.evaluate(None)
            ensure(result).equals(expected)

    def test_it_should_perform_a_complex_comparison_on_a_default_value(self):
        for cmp, expected in [('=', False), ('>=', False), ('<=', True), ('<', True)]:
            comparison = types.Comparison(
                quality = 'Foo',
                comparator = cmp,
                expression = types.Expression(
                    term1 = 5,
                    operator = '-',
                    term2 = 3,
                ),
            )
            result = comparison.evaluate(None)
            ensure(result).equals(expected)

    def test_it_should_perform_a_simple_comparison_on_an_existing_value(self):
        for cmp, expected in [('=', True), ('>=', True), ('<=', True), ('<', False)]:
            comparison = types.Comparison(
                quality = 'Foo',
                comparator = cmp,
                expression = 2,
            )
            result = comparison.evaluate(2)
            ensure(result).equals(expected)

    def test_it_should_perform_a_complex_comparison_on_an_existing_value(self):
        for cmp, expected in [('=', True), ('>=', True), ('<=', True), ('<', False)]:
            comparison = types.Comparison(
                quality = 'Foo',
                comparator = cmp,
                expression = types.Expression(
                    term1 = 5,
                    operator = '-',
                    term2 = 3,
                ),
            )
            result = comparison.evaluate(2)
            ensure(result).equals(expected)


# class EffectTests(TestCase):
#     def test_it_should_perform_an_effect(self):
#         effect = types.Effect(

#         )


class ExpressionTests(TestCase):
    def test_it_should_evaluate_a_simple_expression(self):
        exp = types.Expression(
            term1 = 1,
            operator = '+',
            term2 = 1,
        )
        result = exp.evaluate()
        ensure(result).equals(2)

    def test_it_should_evaluate_a_complex_expression(self):
        exp = types.Expression(
            term1 = types.Expression(
                term1 = 5,
                operator = '*',
                term2 = 5,
            ),
            operator = '+',
            term2 = types.Expression(
                term1 = 5,
                operator = '*',
                term2 = 5,
            ),
        )
        result = exp.evaluate()
        ensure(result).equals(50)


class OperationTests(TestCase):
    def test_it_should_perform_a_simple_operation_on_a_default_value(self):
        for op, expected in [('=', 2), ('+=', 2), ('-=', -2), ('*=', 0)]:
            operation = types.Operation(
                quality = 'Foo',
                operator = op,
                expression = 2,
                constraint = None,
            )
            result = operation.evaluate(None)
            ensure(result).equals(expected)

    def test_it_should_perform_a_complex_operation_on_a_default_value(self):
        for op, expected in [('=', 2), ('+=', 2), ('-=', -2), ('*=', 0)]:
            operation = types.Operation(
                quality = 'Foo',
                operator = op,
                expression = types.Expression(
                    term1 = 5,
                    operator = '-',
                    term2 = 3,
                ),
                constraint = None,
            )
            result = operation.evaluate(None)
            ensure(result).equals(expected)

    def test_it_should_perform_a_simple_operation_on_an_existing_value(self):
        for op, expected in [('=', 2), ('+=', 4), ('-=', 0), ('*=', 4)]:
            operation = types.Operation(
                quality = 'Foo',
                operator = op,
                expression = 2,
                constraint = None,
            )
            result = operation.evaluate(2)
            ensure(result).equals(expected)

    def test_it_should_perform_a_complex_operation_on_an_existing_value(self):
        for op, expected in [('=', 2), ('+=', 4), ('-=', 0), ('*=', 4)]:
            operation = types.Operation(
                quality = 'Foo',
                operator = op,
                expression = types.Expression(
                    term1 = 5,
                    operator = '-',
                    term2 = 3,
                ),
                constraint = None,
            )
            result = operation.evaluate(2)
            ensure(result).equals(expected)
