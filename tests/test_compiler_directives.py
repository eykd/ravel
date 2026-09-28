from unittest.mock import Mock

import pytest

from ravel import exceptions, types
from ravel.compiler import directives


class TestCompileDirective:
    def test_it_should_handle_text_directives(self, env):
        result = directives.compile_directive(env, "Situation", Mock(), {"text": "Hello world"})
        expected = [(types.Text(text="Hello world"), {})]
        assert result == expected

    def test_it_should_handle_a_list_of_effects(self, env):
        effects = {
            "effect": ["foo = 1", "bar = 2"],
        }
        result = directives.compile_directive(env, "Situation", Mock(), effects)
        expected = [
            (types.Operation(quality="foo", operator="=", expression=1), {}),
            (types.Operation(quality="bar", operator="=", expression=2), {}),
        ]
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
            {
                "parent::hello-world": types.Situation(
                    intro=types.Text(text="Hello, world!"),
                    directives=[types.Text(text="Hello, world!")],
                )
            },
        )
        assert result == expected

    def test_it_should_namespace_a_nested_choice_under_its_parent_choice(self, env):
        """A ``choice:`` nested inside another ``choice:`` body namespaces under its immediate
        parent choice, not the grandparent rule -- so sibling nested choices with the same
        wording at different depths never collide."""
        result = directives.compile_choice(
            env,
            "Situation",
            "parent",
            [
                "Outer choice text.",
                {
                    "choice": [
                        "Inner choice text.",
                        {"effect": "Foo = 1"},
                    ]
                },
            ],
        )
        choice, locations = result
        assert choice == types.Choice(choice="parent::outer-choice-text")
        assert "parent::outer-choice-text::inner-choice-text" in locations
        inner = locations["parent::outer-choice-text::inner-choice-text"]
        assert inner.directives == [types.Text(text="Inner choice text."), types.Operation("Foo", "=", 1)]
        outer = locations["parent::outer-choice-text"]
        assert outer.directives == [
            types.Text(text="Outer choice text."),
            types.BeginChoices(),
            types.Choice(choice="parent::outer-choice-text::inner-choice-text"),
            types.GetChoice(),
        ]


class TestCompileChoiceNestingDepth:
    @staticmethod
    def _build_nested_choice_body(depth):
        """Build a choice body nested ``depth`` levels deep, without a giant fixture file."""
        body = "Innermost text."
        for _ in range(depth):
            body = ["Intro text.", {"choice": body}]
        return body

    def test_it_should_raise_parse_error_at_the_boundary_depth(self, env):
        """One level past the configured limit must raise ParseError, not RecursionError."""
        body = self._build_nested_choice_body(directives.MAX_CHOICE_NESTING_DEPTH + 1)

        with pytest.raises(exceptions.ParseError):
            directives.compile_choice(env, "Situation", "parent", body)

    def test_it_should_compile_at_exactly_the_boundary_depth(self, env):
        """Nesting depth exactly at the configured limit must still compile successfully."""
        body = self._build_nested_choice_body(directives.MAX_CHOICE_NESTING_DEPTH)

        # Should not raise.
        directives.compile_choice(env, "Situation", "parent", body)


class TestCompileChoiceFailure:
    def test_it_should_wrap_a_situation_construction_failure(self, env, monkeypatch):
        """A broken Situation must surface as a ParseError chained from the cause."""

        def explode(*args, **kwargs):
            raise TypeError("bad situation")

        monkeypatch.setattr(types, "Situation", explode)

        with pytest.raises(exceptions.ParseError) as excinfo:
            directives.compile_choice(env, "Situation", "test::rule", ["Some intro text."])

        assert excinfo.value.args[0] == "TypeError: bad situation"
        assert isinstance(excinfo.value.__cause__, TypeError)
