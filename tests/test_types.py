from unittest import TestCase

from ensure import ensure

from ravel import types


class TextTests(TestCase):
    def test_it_should_stringify_nicely(self):
        text = types.Text('Some plain text.')
        ensure(str(text)).equals('Some plain text.')
