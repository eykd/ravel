from unittest import TestCase
from ensure import ensure

from ravel import exceptions
from ravel import types

from .helpers import source


class TestRaiseParseError(TestCase):
    def test_it_should_raise_a_parse_error_for_known_source(self):
        (ensure(exceptions.raise_parse_error)
         .called_with(source('foo'))
         .raises(exceptions.ParseError))

    def test_it_should_raise_a_custom_parse_error_for_known_source(self):
        (ensure(exceptions.raise_parse_error)
         .called_with(source('foo'), exceptions.ComparisonParseError)
         .raises(exceptions.ComparisonParseError))

    def test_it_should_raise_a_parse_error_for_unknown_source(self):
        (ensure(exceptions.raise_parse_error)
         .called_with('foo')
         .raises(exceptions.ParseError))

    def test_it_should_raise_a_custom_parse_error_for_known_source(self):
        (ensure(exceptions.raise_parse_error)
         .called_with('foo', exceptions.ComparisonParseError)
         .raises(exceptions.ComparisonParseError))
