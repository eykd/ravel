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
