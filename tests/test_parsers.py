import itertools as it

import parsimonious.expressions
import pytest
from hypothesis import given
from hypothesis import strategies as st

from ravel import exceptions, parsers, types


class TestIntroTextParser:
    @pytest.fixture
    def parser(self):
        return parsers.IntroTextParser()

    @pytest.mark.parametrize("text", ["Price: 5 [approx", "\x1b[2J", "[x"])
    def test_it_should_raise_parse_error_for_an_unclosed_bracket(self, parser, text):
        with pytest.raises(exceptions.ParseError, match="Invalid intro text") as excinfo:
            parser.parse(text)

        assert isinstance(excinfo.value.__cause__, exceptions.ParsimoniousParseError)

    def test_it_should_bound_the_invalid_intro_text_message(self, parser):
        with pytest.raises(exceptions.ParseError) as excinfo:
            parser.parse("[" * 900_000)

        assert len(str(excinfo.value)) < 512

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

    @pytest.mark.parametrize("text", ["a <> b", "a<><>", "{x == 1} a <> b", "<> a", "\x1b[2J <> b"])
    def test_it_should_raise_parse_error_for_glue_before_the_end_of_the_line(self, parser, text):
        with pytest.raises(
            exceptions.ParseError, match="Invalid text line.*glue is only allowed at the end"
        ) as excinfo:
            parser.parse(text)

        assert isinstance(excinfo.value.__cause__, exceptions.ParsimoniousParseError)
        assert "\x1b" not in str(excinfo.value)

    def test_it_should_bound_the_invalid_text_line_message(self, parser):
        with pytest.raises(exceptions.ParseError) as excinfo:
            parser.parse("<>" * 900_000)

        assert len(str(excinfo.value)) < 512

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
            types.Expression(types.Expression(3, "+", 2), "+", 3),
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
                types.Expression(
                    types.Expression(5, "*", 2),
                    "/",
                    types.Expression(3, "-", 2),
                ),
            ),
            None,
        )
        result = parser.parse(statement)
        print("Got", result)
        print("Exp", expected)
        assert isinstance(result, types.Operation)
        assert result == expected

    @pytest.mark.parametrize(
        ("text", "rhs"),
        [
            ("X = 10 - 4 - 2", types.Expression(types.Expression(10, "-", 4), "-", 2)),
            ("X = 8 / 4 / 2", types.Expression(types.Expression(8, "/", 4), "/", 2)),
            ("X = 2 + 3 * 4", types.Expression(2, "+", types.Expression(3, "*", 4))),
            (
                "X = 8 // 2 * 3 % 5",
                types.Expression(types.Expression(types.Expression(8, "//", 2), "*", 3), "%", 5),
            ),
            ("X = (1 + 2) * 3", types.Expression(types.Expression(1, "+", 2), "*", 3)),
            ("X = 10-4", types.Expression(10, "-", 4)),
        ],
    )
    def test_arithmetic_parses_left_associative_with_two_precedence_tiers(self, parser, text, rhs):
        assert parser.parse(text) == types.Operation("X", "=", rhs, None)

    @pytest.mark.parametrize("text", ["X=5", "X>1"])
    def test_setters_and_comparators_require_surrounding_whitespace(self, parser, text):
        with pytest.raises(Exception):  # noqa: B017, PT011
            parser.parse(text)

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

    @pytest.mark.parametrize(
        ("text", "rhs"),
        [
            ("X = -5", -5),
            ("X = -1.5", -1.5),
            ("X = 10 - -4", types.Expression(10, "-", -4)),
            ("X = 10 -4", types.Expression(10, "-", 4)),
            ('X = ""', ""),
        ],
    )
    def test_signed_number_literals_and_empty_strings_parse(self, parser, text, rhs):
        assert parser.parse(text) == types.Operation("X", "=", rhs, None)

    @pytest.mark.parametrize(
        ("text", "op", "con", "bound"),
        [
            ("X += 1 max -5", "+=", "max", -5),
            ("X -= 3 min -2", "-=", "min", -2),
        ],
    )
    def test_constraint_bounds_may_be_negative(self, parser, text, op, con, bound):
        value = 1 if op == "+=" else 3
        assert parser.parse(text) == types.Operation("X", op, value, types.Constraint(con, bound))

    def test_unary_minus_on_a_group_is_rejected(self, parser):
        with pytest.raises(Exception):  # noqa: B017, PT011
            parser.parse("X = -(1 + 2)")


class TestComparisonParserSignedNumbers:
    def test_comparison_against_a_negative_number_parses(self):
        assert parsers.ComparisonParser().parse("Health > -1") == types.Comparison("Health", ">", -1)


class TestOperationParserQualityReferences:
    @pytest.fixture
    def parser(self):
        return parsers.OperationParser()

    @pytest.mark.parametrize(
        ("text", "rhs"),
        [
            ("X = [Health] + Bonus", types.Expression(types.QualityRef("Health"), "+", types.QualityRef("Bonus"))),
            ("X = Health + 1", types.Expression(types.QualityRef("Health"), "+", 1)),
            ("X = values", types.QualityRef("values")),
            ("X = maxHealth", types.QualityRef("maxHealth")),
            ("X = Été + 1", types.Expression(types.QualityRef("Été"), "+", 1)),
            ("X = Has-Key", types.Expression(types.QualityRef("Has"), "-", types.QualityRef("Key"))),
            ("X = [Has-Key]", types.QualityRef("Has-Key")),
        ],
    )
    def test_identifiers_and_bracketed_names_parse_as_quality_references(self, parser, text, rhs):
        assert parser.parse(text) == types.Operation("X", "=", rhs, None)

    def test_a_quality_reference_may_take_a_constraint(self, parser):
        result = parser.parse("X = Health max 3")
        assert result == types.Operation("X", "=", types.QualityRef("Health"), types.Constraint("max", 3))

    @pytest.mark.parametrize("subject", ["Has-Key", "value", "Wearing Cloak", "Has Key"])
    def test_subjects_keep_their_names(self, parser, subject):
        text = {
            "Has-Key": "Has-Key = 5",
            "value": "value = 3",
            "Wearing Cloak": '"Wearing Cloak" = 0',
            "Has Key": "[Has Key] = 1",
        }[subject]
        assert parser.parse(text).quality == subject

    @pytest.mark.parametrize("text", ["X = min + 1", "X = max", "X = -Health"])
    def test_reserved_words_and_unary_minus_on_names_are_rejected(self, parser, text):
        with pytest.raises(Exception):  # noqa: B017, PT011
            parser.parse(text)


class TestValueKeyword:
    """`value` is the keyword for the subject's current value, in operations and comparisons."""

    @pytest.mark.parametrize(
        ("text", "rhs"),
        [
            ("X += value", types.VALUE),
            ("X += value * 2", types.Expression(types.VALUE, "*", 2)),
            ("X = 3 + value", types.Expression(3, "+", types.VALUE)),
        ],
    )
    def test_value_compiles_to_value_in_operations(self, text, rhs):
        result = parsers.OperationParser().parse(text)
        assert result.expression == rhs

    def test_value_compiles_to_value_in_comparisons(self):
        assert parsers.ComparisonParser().parse("Score > value") == types.Comparison("Score", ">", types.VALUE)

    def test_value_compiles_inside_a_comparison_expression(self):
        result = parsers.ComparisonParser().parse("Score == value * 2")
        assert result == types.Comparison("Score", "==", types.Expression(types.VALUE, "*", 2))

    def test_value_keyword_does_not_swallow_longer_identifiers(self):
        result = parsers.OperationParser().parse("X = valuable")
        assert result.expression == types.QualityRef("valuable")

    def test_value_keyword_is_distinct_from_quality_references(self):
        result = parsers.OperationParser().parse("X = value + Value")
        assert result.expression == types.Expression(types.VALUE, "+", types.QualityRef("Value"))


class TestOperationParserConstraintRules:
    """A constraint clamps a numeric result: one per operation, bound a number literal, never on a string."""

    @pytest.mark.parametrize(
        "text",
        [
            'X = "a" max 3',
            "X += 1 min 0 max 8",
            "X += 1 max value",
        ],
    )
    def test_an_invalid_constraint_is_an_operation_parse_error_naming_the_operation(self, text):
        with pytest.raises(exceptions.OperationParseError) as excinfo:
            parsers.OperationParser().parse(text)

        assert text in str(excinfo.value)


class TestExpressionOperandLimit:
    """Deep left-folded chains must fail at compile time, never as a raw RecursionError at runtime."""

    @staticmethod
    def _chain(count, operator="+"):
        return operator.join(["1"] * count)

    @pytest.mark.parametrize("operator", ["+", "*"])
    def test_a_chain_at_the_limit_parses_and_evaluates(self, operator):
        operation = parsers.OperationParser().parse("X = " + self._chain(parsers.MAX_EXPRESSION_OPERANDS, operator))

        assert operation.evaluate(0) == (parsers.MAX_EXPRESSION_OPERANDS if operator == "+" else 1)

    @pytest.mark.parametrize("operator", ["+", "*"])
    def test_an_operation_over_the_limit_raises_a_parse_error_naming_the_limit(self, operator):
        text = "X = " + self._chain(parsers.MAX_EXPRESSION_OPERANDS + 1, operator)

        with pytest.raises(exceptions.OperationParseError, match=str(parsers.MAX_EXPRESSION_OPERANDS)):
            parsers.OperationParser().parse(text)

    def test_a_comparison_over_the_limit_raises_a_parse_error(self):
        text = "X == " + self._chain(parsers.MAX_EXPRESSION_OPERANDS + 1)

        with pytest.raises(exceptions.ComparisonParseError, match=str(parsers.MAX_EXPRESSION_OPERANDS)):
            parsers.ComparisonParser().parse(text)

    def test_nested_chains_at_the_limit_evaluate_without_recursion_error(self):
        term = self._chain(parsers.MAX_EXPRESSION_OPERANDS, "*")
        text = "X = " + "+".join([term] * parsers.MAX_EXPRESSION_OPERANDS)

        assert parsers.OperationParser().parse(text).evaluate(0) == parsers.MAX_EXPRESSION_OPERANDS


class TestExpressionLengthLimit:
    """Over-long expression text is refused before Parsimonious builds a parse tree for it."""

    @staticmethod
    def _padded(prefix, length):
        return prefix + " " * (length - len(prefix) - 1) + "1"

    def test_an_operation_at_the_limit_parses(self):
        text = self._padded("X = ", parsers.MAX_EXPRESSION_LENGTH)

        assert len(text) == parsers.MAX_EXPRESSION_LENGTH
        assert parsers.OperationParser().parse(text).evaluate(0) == 1

    def test_a_comparison_at_the_limit_parses(self):
        text = self._padded("X == ", parsers.MAX_EXPRESSION_LENGTH)

        assert parsers.ComparisonParser().parse(text) is not None

    def test_a_full_chain_with_long_quality_names_fits_under_the_limit(self):
        name = "q" * 100
        text = "X = " + "+".join([name] * parsers.MAX_EXPRESSION_OPERANDS)

        assert len(text) < parsers.MAX_EXPRESSION_LENGTH
        assert parsers.OperationParser().parse(text).quality == "X"

    @pytest.mark.parametrize(
        ("parser", "error", "prefix"),
        [
            (parsers.OperationParser, exceptions.OperationParseError, "X = "),
            (parsers.ComparisonParser, exceptions.ComparisonParseError, "X == "),
        ],
    )
    def test_text_over_the_limit_is_rejected_without_reaching_parsimonious(self, monkeypatch, parser, error, prefix):
        def boom(*args, **kwargs):
            raise AssertionError("parsimonious was reached")

        monkeypatch.setattr(parsers.NodeVisitor, "parse", boom)
        text = prefix + "+".join(["x"] * 200_000)

        with pytest.raises(error, match=str(parsers.MAX_EXPRESSION_LENGTH)):
            parser().parse(text)

    def test_a_long_plain_text_line_still_parses(self):
        text = "word " * 40_000

        assert len(text) > parsers.MAX_EXPRESSION_LENGTH
        assert parsers.PlainTextParser().parse(text).text.startswith("word")

    @pytest.mark.parametrize(
        "template",
        [
            "{q == %s} hello",
            "{q == %s",
            '{q == "}" + %s} hello',
        ],
        ids=["closed", "unclosed", "brace-in-string"],
    )
    def test_an_oversized_text_line_prefix_is_refused_before_parsing(self, monkeypatch, template):
        def boom(*args, **kwargs):
            raise AssertionError("the grammar must not run")

        monkeypatch.setattr(parsers.NodeVisitor, "parse", boom)
        text = template % "+".join(["1"] * 500_000)

        with pytest.raises(exceptions.ComparisonParseError, match=str(parsers.MAX_EXPRESSION_LENGTH)):
            parsers.PlainTextParser().parse(text)

    def test_a_long_prose_tail_after_a_short_prefix_still_parses(self):
        text = "{q == 1} " + "word } " * 40_000

        assert len(text) > parsers.MAX_EXPRESSION_LENGTH
        assert parsers.PlainTextParser().parse(text).predicate is not None

    def test_a_long_unprefixed_prose_line_still_parses(self):
        assert parsers.PlainTextParser().parse("x" * 500_000).text == "x" * 500_000

    @pytest.mark.parametrize(
        "template",
        [
            '{x == [a}] + "%s"} hi',
            '{[q}] == "%s"} hi',
            '{q}} == "%s"} hi',
        ],
        ids=["brace-in-bracketed-operand", "brace-in-bracketed-quality", "brace-in-unquoted-quality"],
    )
    def test_a_brace_the_grammar_consumes_does_not_shorten_the_measured_prefix(self, monkeypatch, template):
        """ravel-h6v.21: a "}" inside [brackets] or an unquoted name once ended a hand regex's scan early."""
        seen = []
        real_match = parsimonious.expressions.Expression.match

        def spy(self, text, pos=0):
            seen.append(len(text))
            return real_match(self, text, pos)

        monkeypatch.setattr(parsimonious.expressions.Expression, "match", spy)
        text = template % ("a" * 200_000)

        with pytest.raises(exceptions.ComparisonParseError, match=str(parsers.MAX_EXPRESSION_LENGTH)):
            parsers.PlainTextParser().parse(text)
        assert seen
        assert max(seen) <= parsers.MAX_EXPRESSION_LENGTH + 2

    @pytest.mark.parametrize(
        ("text", "prose"),
        [('{x == "a}b"} prose', " prose"), ("{x == 1} prose with a } brace", " prose with a } brace")],
    )
    def test_a_brace_in_a_string_or_in_the_prose_keeps_its_meaning(self, text, prose):
        result = parsers.PlainTextParser().parse(text)

        assert result.text == prose
        assert result.predicate is not None

    def test_a_short_line_whose_brace_opens_no_predicate_is_prose(self):
        assert parsers.PlainTextParser().parse("{foo bar} hi") == types.Text("{foo bar} hi")

    @given(st.text(alphabet='{}[]"q =1+a<>', max_size=60))
    def test_an_accepted_line_never_has_a_prefix_longer_than_the_cap(self, line):
        """Property: whatever the line, the predicate prefix the parser accepts is at most the cap."""
        cap = 8
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(parsers, "MAX_EXPRESSION_LENGTH", cap)
            try:
                result = parsers.PlainTextParser().parse(line)
            except exceptions.ComparisonParseError:
                assert len(line) > cap + 2
                return
            except exceptions.ParseError:
                return  # prose holding "<>" before its end is malformed, as it always was
        prefix_length = len(line) - len(result.text) - (2 if result.sticky else 0)
        assert prefix_length <= cap + 2
        assert (prefix_length > 0) == (result.predicate is not None)


class TestExpressionDepthLimit:
    """Parentheses let capped chains nest; total depth and paren nesting are capped too."""

    @staticmethod
    def _wrapped(levels):
        """A full chain wrapped in parentheses `levels` times, each wrap extended by a full chain."""
        text = "+".join(["1"] * parsers.MAX_EXPRESSION_OPERANDS)
        for _ in range(levels):
            text = "(" + text + ")" + "+1" * (parsers.MAX_EXPRESSION_OPERANDS - 1)
        return text

    def test_parentheses_over_the_limit_raise_a_typed_error(self):
        text = "X = " + "(" * (parsers.MAX_PAREN_DEPTH + 1) + "1" + ")" * (parsers.MAX_PAREN_DEPTH + 1)

        with pytest.raises(exceptions.OperationParseError, match=str(parsers.MAX_PAREN_DEPTH)):
            parsers.OperationParser().parse(text)

    def test_comparison_parentheses_over_the_limit_raise_a_typed_error(self):
        text = "X == " + "(" * 300 + "1" + ")" * 300

        with pytest.raises(exceptions.ComparisonParseError):
            parsers.ComparisonParser().parse(text)

    def test_parentheses_at_the_limit_parse(self):
        n = parsers.MAX_PAREN_DEPTH
        assert parsers.OperationParser().parse("X = " + "(" * n + "1" + ")" * n).evaluate(0) == 1

    def test_unbalanced_closers_do_not_count_as_nesting(self):
        with pytest.raises(exceptions.ParseError):
            parsers.OperationParser().parse("X = 1" + ")" * 50)

    def test_nested_chains_over_the_depth_limit_raise_a_typed_error(self):
        with pytest.raises(exceptions.OperationParseError, match=str(parsers.MAX_EXPRESSION_DEPTH)):
            parsers.OperationParser().parse("X = " + self._wrapped(3))

    def test_the_deepest_accepted_expression_evaluates_without_recursion_error(self):
        operation = parsers.OperationParser().parse("X = " + self._wrapped(1))

        assert operation.evaluate(0) == 2 * parsers.MAX_EXPRESSION_OPERANDS - 1


class TestOversizedIntegerLiterals:
    DIGITS = "9" * 5000

    def test_operation_literal_over_the_int_limit_raises_a_typed_error(self):
        with pytest.raises(exceptions.OperationParseError, match="too many digits"):
            parsers.OperationParser().parse("X = " + self.DIGITS)

    def test_comparison_literal_over_the_int_limit_raises_a_typed_error(self):
        with pytest.raises(exceptions.ComparisonParseError, match="too many digits"):
            parsers.ComparisonParser().parse("X == " + self.DIGITS)
