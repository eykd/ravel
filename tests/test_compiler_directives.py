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


class TestBoundedDirectiveMessages:
    def test_it_should_bound_the_too_many_directives_message(self, env):
        raw = {"text": "a" * 450_000, "effect": "b" * 450_000}
        with pytest.raises(exceptions.ParseError) as info:
            directives.compile_directive(env, "Situation", Mock(), raw)

        assert len(str(info.value)) < 512

    def test_it_should_bound_the_unknown_directive_message(self, env):
        with pytest.raises(exceptions.ParseError) as info:
            directives.compile_directive(env, "Situation", Mock(), {"k\x1b[2J" * 100: "v" * 900_000})

        assert len(str(info.value)) < 512
        assert "\x1b" not in str(info.value)

    def test_it_should_bound_the_unrecognized_effect_and_end_block_messages(self, env):
        with pytest.raises(exceptions.ParseError) as info:
            directives.compile_directive(env, "Situation", Mock(), {"effect": {"k": "v" * 900_000}})
        assert len(str(info.value)) < 512

        with pytest.raises(exceptions.ParseError) as info:
            directives.compile_directive(env, "Situation", Mock(), {"end": {"k": "v" * 900_000}})
        assert len(str(info.value)) < 512

    def test_it_should_bound_the_no_text_found_message(self):
        from ravel.utils.strings import get_text

        with pytest.raises(exceptions.ParseError) as info:
            get_text(["z" * 900_000])

        assert len(str(info.value)) < 512

    def test_it_should_bound_an_invalid_operation_message(self):
        from ravel import parsers

        with pytest.raises(exceptions.OperationParseError) as info:
            parsers.OperationParser().parse("!" * 900_000)

        assert len(str(info.value)) < 512


class TestSiblingChoiceSlugCollisions:
    @staticmethod
    def _compile(env, *raw_directives):
        return directives.compile_directives(env, "Situation", "parent", ["Intro.", *raw_directives])

    @pytest.mark.parametrize(("first", "second"), [("[Go]A", "[Go!]B"), ("[Go]A", "[go]B"), ("[]A", "[]B")])
    def test_it_should_reject_sibling_choices_in_one_menu_that_share_a_slug(self, env, first, second):
        with pytest.raises(exceptions.ParseError, match="Sibling choices") as excinfo:
            self._compile(env, {"choice": [first]}, {"choice": [second]})
        assert "slugify" in str(excinfo.value)

    def test_it_should_name_both_labels_and_the_slug(self, env):
        with pytest.raises(exceptions.ParseError) as excinfo:
            self._compile(env, {"choice": ["[Go]A"]}, {"choice": ["[Go!]B"]})
        message = str(excinfo.value)
        assert "Go" in message
        assert "Go!" in message
        assert "'go'" in message

    def test_it_should_allow_the_same_label_in_separate_menus(self, env):
        _, _, subsituations = self._compile(
            env, {"choice": ["[Go on]A"]}, {"effect": "Foo = 1"}, {"choice": ["[Go on]B"]}
        )
        assert len(subsituations) == 3

    def test_it_should_allow_non_colliding_siblings(self, env):
        _, _, subsituations = self._compile(env, {"choice": ["[Go]A"]}, {"choice": ["[Stay]B"]})
        assert len(subsituations) == 2
