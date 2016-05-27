import itertools as it
from unittest import TestCase
from ensure import ensure

from ravel.expressions import Expression, VALUE
from ravel import operations


class TestOperationsParser(TestCase):
    def setUp(self):
        self.parser = operations.OperationParser()
        self.setters = ('+=', '-=', '/=', '//=', '*=', '%=', '=')
        self.values = (3, 3.0, 5, 5.0)
        self.constraints = ('min', 'max')
        self.quote_styles = ('"', "'", '`', '"""', "'''", '```')

    def test_it_should_handle_a_simple_quality_name(self):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = operations.Operation(
            'Man of Honor', '+=', Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(operations.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression(self):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = operations.Operation(
            'Man of Honor', '+=', Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(operations.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression_with_a_value(self):
        statement = '"Man of Honor" += 3 * value'
        print(statement)
        expected = operations.Operation(
            'Man of Honor', '+=', Expression(3, '*', VALUE), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(operations.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_more_complicated_expressions(self):
        statement = '"Man of Honor" += 3 + 2 + 3'
        print(statement)
        expected = operations.Operation(
            'Man of Honor', '+=',
            Expression(
                3, '+',
                Expression(2, '+', 3)),
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(operations.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_complex_expression(self):
        statement = '"Man of Honor" += 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = operations.Operation(
            'Man of Honor', '+=',
            Expression(
                3, '+',
                Expression(
                    5, '*',
                    Expression(
                        2, '/',
                        Expression(3, '-', 2)
                    )
                )
            ),
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(operations.Operation)
        ensure(result).equals(expected)

    def test_it_should_set_a_string(self):
        for qs in self.quote_styles:
            statement = '"Man of Honor" = %(qs)sYes%(qs)s' % {
                'qs': qs,
            }
            expected = operations.Operation(
                'Man of Honor', '=', 'Yes', None)
            result = self.parser.parse(statement)
            ensure(result).is_an(operations.Operation)
            ensure(result).equals(expected)

    def test_it_should_parse_all_operators_with_numbers(self):
        for op, val in it.product(self.setters, self.values):
            statement = '"Man of Honor" %(op)s %(val)s' % {'op': op, 'val': val}
            expected = operations.Operation('Man of Honor', op, val, None)
            result = self.parser.parse(statement)
            ensure(result).is_an(operations.Operation)
            ensure(result).equals(expected)

    def test_it_should_parse_all_operators_with_numbers_and_a_constraint(self):
        factors =  it.product(self.setters, self.values, self.constraints, self.values)
        for op, val, con, conval in factors:
            statement = '"Man of Honor" %(op)s %(val)s %(con)s %(conval)s' % {
                'op': op,
                'val': val,
                'con': con,
                'conval': conval,
            }
            expected = operations.Operation(
                'Man of Honor', op, val,
                operations.Constraint(con, conval)
            )
            result = self.parser.parse(statement)
            ensure(result).is_an(operations.Operation)
            ensure(result).equals(expected)
