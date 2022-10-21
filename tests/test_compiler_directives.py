from unittest.mock import Mock

import pytest

from pyrsistent import pmap, pvector

from ravel import exceptions, types
from ravel.compiler import directives


class TestCompileDirective:
    def test_it_should_handle_text_directives(self, env):
        result = directives.compile_directive(env, "Situation", Mock(), {"text": "Hello world"})
        expected = pvector([(types.Text(text="Hello world"), pmap())])
        assert result == expected

    def test_it_should_handle_a_list_of_effects(self, env):
        effects = {
            "effect": ["foo = 1", "bar = 2"],
        }
        result = directives.compile_directive(env, "Situation", Mock(), effects)
        expected = pvector(
            [
                (types.Operation(quality="foo", operator="=", expression=1), pmap()),
                (types.Operation(quality="bar", operator="=", expression=2), pmap()),
            ]
        )
        assert result == expected

    def test_it_should_raise_parse_error_for_unknown_effect_type(self, env):
        effects = {
            "effect": {"wacky": "effects"},
        }
        with pytest.raises(exceptions.ParseError):
            directives.compile_directive(env, "Situation", Mock(), effects)

    def test_it_should_raise_parse_error_for_unknown_directives(self, env):
        directive = {"foo": "bar"}
        with pytest.raises(exceptions.ParseError):
            directives.compile_directive(env, "Situation", Mock(), directive)


class TestCompileChoice:
    def test_it_should_compile_a_choice_with_only_text(self, env):
        result = directives.compile_choice(env, "Situation", "parent", "Hello, world!")
        expected = (
            types.Choice(choice="parent::hello-world"),
            pmap(
                {
                    "parent::hello-world": types.Situation(
                        intro=types.Text(text="Hello, world!"),
                        directives=pvector([types.Text(text="Hello, world!")]),
                    )
                }
            ),
        )
        assert result == expected
