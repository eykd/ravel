import itertools as it

import pytest

from ravel import parsers, types


class TestIntroTextParser:
    @pytest.fixture
    def parser(self):
        return parsers.IntroTextParser()

    def test_it_should_parse_intro_text_with_an_empty_suffix_and_a_tail(self, parser):
        result = parser.parse('"A wager!"[] I returned.')
        expected = [types.Text('"A wager!"'), types.Text('"A wager!" I returned.')]
        assert result == expected

    def test_it_should_parse_intro_text_with_a_suffix_and_a_tail(self, parser):
        result = parser.parse('"Well then[."]," I said.')
        expected = [
            types.Text('"Well then."'),
            types.Text('"Well then," I said.'),
        ]
        assert result == expected

    def test_it_should_parse_intro_text_with_no_suffix_or_tail(self, parser):
        result = parser.parse('"Well then."')
        expected = [
            types.Text('"Well then."'),
            types.Text('"Well then."'),
        ]
        assert result == expected

    def test_it_should_parse_intro_text_with_only_a_suffix(self, parser):
        result = parser.parse('["Well then."]')
        expected = [
            types.Text('"Well then."'),
            types.Text(""),
        ]
        assert result == expected


class TestPlainTextParser:
    @pytest.fixture
    def parser(self):
        return parsers.PlainTextParser()

    def test_it_should_parse_plain_text_without_features(self, parser):
        result = parser.parse("Nothing to see here. Move along.")
        expected = types.Text("Nothing to see here. Move along.")
        assert result == expected

    def test_it_should_parse_plain_text_with_glue(self, parser):
        result = parser.parse("Caught in a sticky web. <>")
        expected = types.Text("Caught in a sticky web. ", sticky=True)
        assert result == expected

    def test_it_should_parse_plain_text_with_a_predicate(self, parser):
        result = parser.parse('{ foo == "bar" }Foo!')
        expected = types.Text(
            "Foo!",
            sticky=False,
            predicate=types.Predicate(
                "foo",
                types.Comparison("foo", "==", "bar"),
            ),
        )
        assert result == expected

    def test_it_should_parse_plain_text_with_a_predicate_and_glue(self, parser):
        result = parser.parse('{ foo == "bar" }Foo! <>')
        expected = types.Text(
            "Foo! ",
            sticky=True,
            predicate=types.Predicate(
                "foo",
                types.Comparison("foo", "==", "bar"),
            ),
        )
        assert result == expected


class TestOperationsParser:
    @pytest.fixture
    def parser(self):
        return parsers.OperationParser()

    def test_it_should_handle_a_simple_quality_name(self, parser):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = types.Operation("Man of Honor", "+=", types.Expression(3, "*", 2), None)
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    def test_it_should_handle_a_simple_expression(self, parser):
        statement = '"Man of Honor" += 3 * 2'
        print(statement)
        expected = types.Operation("Man of Honor", "+=", types.Expression(3, "*", 2), None)
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    def test_it_should_handle_a_simple_expression_with_a_value(self, parser):
        statement = '"Man of Honor" += 3 * value'
        print(statement)
        expected = types.Operation("Man of Honor", "+=", types.Expression(3, "*", types.VALUE), None)
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    def test_it_should_handle_a_more_complicated_expressions(self, parser):
        statement = '"Man of Honor" += 3 + 2 + 3'
        print(statement)
        expected = types.Operation(
            "Man of Honor",
            "+=",
            types.Expression(3, "+", types.Expression(2, "+", 3)),
            None,
        )
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    def test_it_should_handle_a_complex_expression(self, parser):
        statement = '"Man of Honor" += 3 + 5 * 2 / (3 - 2)'
        print(statement)
        expected = types.Operation(
            "Man of Honor",
            "+=",
            types.Expression(
                3,
                "+",
                types.Expression(5, "*", types.Expression(2, "/", types.Expression(3, "-", 2))),
            ),
            None,
        )
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    @pytest.mark.parametrize("qs", ['"', "'", "`", '"""', "'''", "```"])
    def test_it_should_set_a_string(self, parser, qs):
        statement = '"Man of Honor" = %(qs)sYes%(qs)s' % {
            "qs": qs,
        }
        expected = types.Operation("Man of Honor", "=", "Yes", None)
        result = parser.parse(statement)
        assert isinstance(result, types.Operation)
        assert result == expected

    operations = ("+=", "-=", "/=", "//=", "*=", "%=", "=")
    values = (3, 3.0, 5, 5.0)

    @pytest.mark.parametrize("op,val", list(it.product(operations, values)))
    def test_it_should_parse_all_operators_with_numbers(self, parser, op, val):
        statement = '"Man of Honor" %(op)s %(val)s' % {"op": op, "val": val}
        expected = types.Operation("Man of Honor", op, val, None)
        result = parser.parse(statement)
        assert isinstance(result, types.Operation)
        assert result == expected

    constraints = ("min", "max")

    @pytest.mark.parametrize("op,val,con,conval", list(it.product(operations, values, constraints, values)))
    def test_it_should_parse_all_operators_with_numbers_and_a_constraint(self, parser, op, val, con, conval):
        statement = '"Man of Honor" %(op)s %(val)s %(con)s %(conval)s' % {
            "op": op,
            "val": val,
            "con": con,
            "conval": conval,
        }
        expected = types.Operation("Man of Honor", op, val, types.Constraint(con, conval))
        result = parser.parse(statement)
        assert isinstance(result, types.Operation)
        assert result == expected
