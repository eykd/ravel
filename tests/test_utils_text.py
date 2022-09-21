import re
import textwrap
from unittest import TestCase

import pytest

from ravel.utils import strings
from ravel.types import Pos


class TestStripOuterWhitespace:
    def test_it_should_strip_blank_lines_before_and_after(self):
        text = "   \n\n   \n      \n  Foo\n \n\nBar    \n    \n  \n\n"
        result = strings.strip_outer_whitespace(text)
        assert result == '  Foo\n \n\nBar'

    def test_it_should_strip_empty_lines(self):
        text = "   \n  \n\n   \n"
        result = strings.strip_outer_whitespace(text)
        assert result == ''


@pytest.fixture
def text():
    return textwrap.dedent("""

        foo
            bar
                baz blah blargh
        boo
    """)


class TestGetLine:
    def test_it_should_get_the_line(self, text):
        result = strings.get_line(text, 5)
        expected = "        baz blah blargh\n"
        assert result == expected

    def test_it_should_get_a_blank_str_for_bad_line(self, text):
        result = strings.get_line(text, 99)
        expected = ""
        assert result == expected


class TestGetCoordsOfStrIndex:
    def test_returns_line_and_column_at_start_of_line(self, text):
        match = re.search('foo', text)
        start = match.start()
        result = strings.get_coords_of_str_index(text, start)
        expected = Pos(start, 3, 0)
        assert result == expected

    def test_returns_line_and_column_of_indented_text(self, text):
        match = re.search('bar', text)
        start = match.start()
        result = strings.get_coords_of_str_index(text, start)
        expected = Pos(start, 4, 4)
        assert result == expected

    def test_returns_line_and_column_of_midline_text(self, text):
        match = re.search('blah', text)
        start = match.start()
        result = strings.get_coords_of_str_index(text, start)
        expected = Pos(start, 5, 12)
        assert result == expected

    def test_returns_last_line_and_first_column_of_bad_index(self, text):
        result = strings.get_coords_of_str_index(text, len(text) + 5)
        expected = Pos(len(text), 6, 0)
        assert result == expected
