import itertools as it
from unittest import TestCase

from pprint import pprint
from ensure import EnsureError
from deepdiff import DeepDiff

import ensure

from ravel import types
from ravel import parsers

ensure.unittest_case.maxDiff = None

ensure = ensure.ensure


class IntroTextParserTests(TestCase):
    def setUp(self):
        self.parser = parsers.IntroTextParser()

    def test_it_should_parse_intro_text_with_an_empty_suffix_and_a_tail(self):
        result = self.parser.parse('"A wager!"[] I returned.')
        (ensure(result)
         .equals([
             types.Text('"A wager!"'),
             types.Text('"A wager!" I returned.')
         ]))

    def test_it_should_parse_intro_text_with_a_suffix_and_a_tail(self):
        result = self.parser.parse('"Well then[."]," I said.')
        (ensure(result)
         .equals([
             types.Text('"Well then."'),
             types.Text('"Well then," I said.'),
         ]))

    def test_it_should_parse_intro_text_with_no_suffix_or_tail(self):
        result = self.parser.parse('"Well then."')
        (ensure(result)
         .equals([
             types.Text('"Well then."'),
             types.Text('"Well then."'),
         ]))

    def test_it_should_parse_intro_text_with_only_a_suffix(self):
        result = self.parser.parse('["Well then."]')
        (ensure(result)
         .equals([
             types.Text('"Well then."'),
             types.Text(''),
         ]))


class PlainTextParserTests(TestCase):
    def setUp(self):
        self.parser = parsers.PlainTextParser()

    def test_it_should_parse_plain_text_without_features(self):
        result = self.parser.parse('Nothing to see here. Move along.')
        (ensure(result)
         .equals(types.Text('Nothing to see here. Move along.')))

    def test_it_should_parse_plain_text_with_glue(self):
        result = self.parser.parse('Caught in a sticky web. <>')
        (ensure(result)
         .equals(types.Text('Caught in a sticky web. ', sticky=True)))

    def test_it_should_parse_plain_text_with_a_predicate(self):
        result = self.parser.parse('{ foo == "bar" }Foo!')
        (ensure(result)
         .equals(types.Text(
             'Foo!',
             sticky=False,
             predicate=types.Predicate(
                 'foo',
                 types.Comparison('foo', '==', 'bar'),
             ))))

    def test_it_should_parse_plain_text_with_a_predicate_and_glue(self):
        result = self.parser.parse('{ foo == "bar" }Foo! <>')
        expected = types.Text(
            'Foo! ',
            sticky=True,
            predicate=types.Predicate(
                'foo',
                types.Comparison('foo', '==', 'bar'),
            ),
        )
        (ensure(result).equals(expected))


class TestOperationsParser(TestCase):
    def setUp(self):
        self.parser = parsers.OperationParser()
        self.setters = ('+=', '-=', '/=', '//=', '*=', '%=', '=')
        self.values = (3, 3.0, 5, 5.0)
        self.constraints = ('min', 'max')
        self.quote_styles = ('"', "'", '`', '"""', "'''", '```')

    def test_it_should_handle_a_simple_quality_name(self):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = types.Operation(
            'Man of Honor', '+=', types.Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression(self):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = types.Operation(
            'Man of Honor', '+=', types.Expression(3, '*', 2), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_simple_expression_with_a_value(self):
        statement = '"Man of Honor" += 3 * value'
        print(statement)
        expected = types.Operation(
            'Man of Honor', '+=', types.Expression(3, '*', types.VALUE), None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_more_complicated_expressions(self):
        statement = '"Man of Honor" += 3 + 2 + 3'
        print(statement)
        expected = types.Operation(
            'Man of Honor', '+=',
            types.Expression(
                3, '+',
                types.Expression(2, '+', 3)),
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Operation)
        ensure(result).equals(expected)

    def test_it_should_handle_a_complex_expression(self):
        statement = '"Man of Honor" += 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = types.Operation(
            'Man of Honor', '+=',
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
            None)
        result = self.parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        ensure(result).is_an(types.Operation)
        ensure(result).equals(expected)

    def test_it_should_set_a_string(self):
        for qs in self.quote_styles:
            statement = '"Man of Honor" = %(qs)sYes%(qs)s' % {
                'qs': qs,
            }
            expected = types.Operation(
                'Man of Honor', '=', 'Yes', None)
            result = self.parser.parse(statement)
            ensure(result).is_an(types.Operation)
            ensure(result).equals(expected)

    def test_it_should_parse_all_operators_with_numbers(self):
        for op, val in it.product(self.setters, self.values):
            statement = '"Man of Honor" %(op)s %(val)s' % {'op': op, 'val': val}
            expected = types.Operation('Man of Honor', op, val, None)
            result = self.parser.parse(statement)
            ensure(result).is_an(types.Operation)
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
            expected = types.Operation(
                'Man of Honor', op, val,
                types.Constraint(con, conval)
            )
            result = self.parser.parse(statement)
            ensure(result).is_an(types.Operation)
            ensure(result).equals(expected)
