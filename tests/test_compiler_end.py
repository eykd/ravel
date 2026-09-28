from unittest.mock import Mock

import pytest

from ravel import exceptions, types
from ravel.compiler import directives


class TestCompileEnd:
    def test_it_should_compile_end_with_an_inline_outcome(self, env):
        result = directives.compile_directive(env, "Situation", Mock(), {"end": "won"})
        expected = [(types.End("won"), {})]
        assert result == expected

    def test_it_should_strip_surrounding_whitespace_from_the_outcome(self, env):
        result = directives.compile_directive(env, "Situation", Mock(), {"end": "  lost  "})
        expected = [(types.End("lost"), {})]
        assert result == expected

    def test_it_should_compile_a_bare_end_as_an_empty_outcome(self, env):
        result = directives.compile_directive(env, "Situation", Mock(), {"end": ""})
        expected = [(types.End(""), {})]
        assert result == expected

    def test_it_should_raise_parse_error_for_a_block_value(self, env):
        directive = {"end": ["not", "inline"]}
        with pytest.raises(exceptions.ParseError):
            directives.compile_directive(env, "Situation", Mock(), directive)
