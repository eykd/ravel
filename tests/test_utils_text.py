from unittest import TestCase
from ensure import ensure

from ravel.utils import strings


class TestStripOuterWhitespace(TestCase):
    def test_it_should_strip_blank_lines_before_and_after(self):
        text = "   \n\n   \n      \n  Foo\n \n\nBar    \n    \n  \n\n"
        result = strings.strip_outer_whitespace(text)
        ensure(result).equals('  Foo\n \n\nBar')

    def test_it_should_strip_empty_lines(self):
        text = "   \n  \n\n   \n"
        result = strings.strip_outer_whitespace(text)
        ensure(result).equals('')
