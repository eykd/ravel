import pytest

from ravel import exceptions

from .helpers import source


class TestRaiseParseError:
    def test_it_should_raise_a_parse_error_for_known_source(self):
        with pytest.raises(exceptions.ParseError):
            exceptions.raise_parse_error(source("foo"))

    def test_it_should_raise_a_custom_parse_error_for_known_source(self):
        with pytest.raises(exceptions.ComparisonParseError):
            exceptions.raise_parse_error(source("foo"), exceptions.ComparisonParseError)

    def test_it_should_raise_a_parse_error_for_unknown_source(self):
        with pytest.raises(exceptions.ParseError):
            exceptions.raise_parse_error("foo")


class TestEvaluationError:
    def test_it_should_be_a_value_error(self):
        assert issubclass(exceptions.EvaluationError, ValueError)


class TestPrintable:
    def test_it_should_leave_short_printable_text_unchanged(self):
        assert exceptions.printable("café latte") == "café latte"

    def test_it_should_escape_control_characters(self):
        assert exceptions.printable("a\x1b[31m\nb") == "a\\x1b[31m\\nb"

    def test_it_should_bound_long_text_with_an_ellipsis(self):
        shown = exceptions.printable("x" * 900_000)

        assert shown == "x" * exceptions.MAX_EXCERPT_LENGTH + exceptions.ELLIPSIS

    def test_it_should_escape_lone_surrogates(self):
        assert exceptions.printable("\ud800") == "\\ud800"

    def test_it_should_render_the_repr_of_a_value_within_the_bound(self):
        assert exceptions.bounded_repr("foo") == "'foo'"
        assert len(exceptions.bounded_repr(["y" * 900_000])) <= exceptions.MAX_EXCERPT_LENGTH + 1


class TestBoundedMessages:
    def test_it_should_bound_the_message_for_a_huge_source(self):
        with pytest.raises(exceptions.ParseError) as info:
            exceptions.raise_parse_error(source("p" * 60_000))

        assert len(str(info.value.args[0])) < 512
        assert info.value.args[1].text == "p" * 60_000

    def test_it_should_bound_the_message_for_unknown_source(self):
        with pytest.raises(exceptions.ParseError) as info:
            exceptions.raise_parse_error("q" * 900_000)

        assert len(str(info.value.args[0])) < 512
