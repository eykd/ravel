import itertools as it
from unittest import TestCase
from ensure import ensure
from parsimonious import nodes

from ravel import parsers


class TestOperationsParser(TestCase):
    def setUp(self):
        self.parser = parsers.OperationParser()
        self.setters = ('+=', '-=', '/=', '//=', '*=', '%=', '=')
        self.values = (3, 3.0, 5, 5.0)
        self.constraints = ('min', 'max')
        self.quote_styles = ('"', "'", '`', '"""', "'''", '```')

    def test_it_should_handle_a_simple_quality_name(self):
        statement = 'Honor += 3 * 2'
        print(statement)
        expected = parsers.Operation(
            'Honor', '+=', parsers.Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression(self):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = parsers.Operation(
            'Man of Honor', '+=', parsers.Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression_with_a_value(self):
        statement = '"Man of Honor" += 3 * value'
        print(statement)
        expected = parsers.Operation(
            'Man of Honor', '+=', parsers.Expression(3, '*', parsers.VALUE), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_more_complicated_expressions(self):
        statement = '"Man of Honor" += 3 + 2 + 3'
        print(statement)
        expected = parsers.Operation(
            'Man of Honor', '+=',
            parsers.Expression(
                3, '+',
                parsers.Expression(2, '+', 3)),
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_complex_expression(self):
        statement = '"Man of Honor" += 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = parsers.Operation(
            'Man of Honor', '+=',
            parsers.Expression(
                3, '+',
                parsers.Expression(
                    5, '*',
                    parsers.Expression(
                        2, '/',
                        parsers.Expression(3, '-', 2)
                    )
                )
            ),
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Operation)
        ensure(result).equals(expected)

    def test_it_should_set_a_string(self):
        for qs in self.quote_styles:
            statement = '"Man of Honor" = %(qs)sYes%(qs)s' % {
                'qs': qs,
            }
            expected = parsers.Operation(
                'Man of Honor', '=', 'Yes', None)
            result = self.parser.parse(statement)
            ensure(result).is_an(parsers.Operation)
            ensure(result).equals(expected)

    def test_it_should_parse_all_operators_with_numbers(self):
        for op, val in it.product(self.setters, self.values):
            statement = '"Man of Honor" %(op)s %(val)s' % {'op': op, 'val': val}
            expected = parsers.Operation('Man of Honor', op, val, None)
            result = self.parser.parse(statement)
            ensure(result).is_an(parsers.Operation)
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
            expected = parsers.Operation(
                'Man of Honor', op, val,
                parsers.Constraint(con, conval)
            )
            result = self.parser.parse(statement)
            ensure(result).is_an(parsers.Operation)
            ensure(result).equals(expected)



class TestComparisonParser(TestCase):
    def setUp(self):
        self.parser = parsers.ComparisonParser()
        self.comparisons = ('<', '<=', '>', '>=', '==', '!=')
        self.values = (3, 3.0, 5, 5.0)
        self.quote_styles = ('"', "'", '`', '"""', "'''", '```')

    def test_it_should_parse_a_simple_quality_name(self):
        factors = it.product(self.comparisons, self.values)
        for comp, val in factors:
            statement = 'Honor %s %s' % (comp, val)
            print(statement)
            expected = parsers.Comparison(
                'Honor', comp, val
            )
            result = self.parser.parse(statement)
            print("Got", result)
            print("Exp", expected)
            ensure(result).is_an(parsers.Comparison)
            ensure(result).equals(expected)

    def test_it_should_parse_a_comparison(self):
        factors = it.product(self.comparisons, self.values)
        for comp, val in factors:
            statement = '"Man of Honor" %s %s' % (comp, val)
            print(statement)
            expected = parsers.Comparison(
                'Man of Honor', comp, val
            )
            result = self.parser.parse(statement)
            print("Got", result)
            print("Exp", expected)
            ensure(result).is_an(parsers.Comparison)
            ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression(self):
        statement = '"Man of Honor" > 3 * 2'
        print(statement)
        expected = parsers.Comparison(
            'Man of Honor', '>', parsers.Expression(3, '*', 2))
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_more_complicated_expressions(self):
        statement = '"Man of Honor" > 3 + 2 + 3'
        print(statement)
        expected = parsers.Comparison(
            'Man of Honor', '>',
            parsers.Expression(
                3, '+',
                parsers.Expression(2, '+', 3)),
        )
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_complex_expression(self):
        statement = '"Man of Honor" > 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = parsers.Comparison(
            'Man of Honor', '>',
            parsers.Expression(
                3, '+',
                parsers.Expression(
                    5, '*',
                    parsers.Expression(
                        2, '/',
                        parsers.Expression(3, '-', 2)
                    )
                )
            ),
        )
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Comparison)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression_with_a_value(self):
        statement = '"Man of Honor" > 3 * value'
        print(statement)
        expected = parsers.Comparison(
            'Man of Honor', '>', parsers.Expression(3, '*', parsers.VALUE))
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(parsers.Comparison)
        ensure(result).equals(expected)
