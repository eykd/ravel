from unittest.mock import patch

import pytest
import syml

from ravel import environments, exceptions, loaders
from ravel.adapters.story_source import MemoryStorySource
from ravel.engine.engine import start
from ravel.engine.story import Story


@pytest.fixture
def env(examples_path):
    return environments.Environment(
        loader=loaders.FileSystemLoader(base_path=examples_path / "simple"),
    )


class TestLoad:
    def test_it_should_load_the_initializing_rulebook(self, env):
        with patch.object(env, "load_rulebook") as mock_loader:
            env.load()
            mock_loader.assert_called_once_with("begin")
            env.initializing_name = "intro"
            mock_loader.reset_mock()
            env.load()
            mock_loader.assert_called_once_with("intro")


class TestGetRulebook:
    def test_it_should_load_the_rulebook_and_its_includes(self, env):
        rulebook = env.load_rulebook("begin")
        assert "begin::intro" in rulebook["rulebook"]["Situation"]["locations"]
        assert "rooms::rooms" in rulebook["rulebook"]["Situation"]["locations"]
        assert "actions::actions" in rulebook["rulebook"]["Situation"]["locations"]

        new_rulebook = env.load_rulebook("begin")
        assert new_rulebook == rulebook


class TestDefaultIsUpToDate:
    def test_it_should_return_true(self, env):
        assert env.default_is_up_to_date() is True


class TestSourcePositions:
    """Parse errors must name the file and line the bad text came from.

    The syml 0.6 upgrade routed loading through ``syml.loads``, which flattens
    every node to a bare ``str`` via ``as_data()``, so ``raise_parse_error``
    could no longer report a position. Loading through ``as_source()`` keeps the
    ``Source`` objects, and the predicate targets must reach
    ``compile_predicate`` unflattened for the position to survive.
    """

    SOURCE = "\n".join(
        [
            "when:",
            "  - this is not a comparison at all",
            "",
            "intro:",
            "",
            "  - Some text.",
        ]
    )

    def test_it_should_report_the_file_and_line_of_a_bad_predicate(self, env):
        with pytest.raises(exceptions.ComparisonParseError) as excinfo:
            env.compile_rulebook(self.SOURCE, name="broken")

        message, position = excinfo.value.args
        assert position.filename == "broken"
        assert position.start.line == 2
        assert position.text == "this is not a comparison at all"
        assert "broken" in message
        assert "Line 2" in message


class TestInjectedLoader:
    def test_it_should_require_a_loader(self):
        with pytest.raises(TypeError):
            environments.Environment()  # type: ignore[call-arg]

    def test_it_should_reject_a_loader_without_a_callable_load(self):
        with pytest.raises(TypeError) as excinfo:
            environments.Environment(loader=object())

        assert str(excinfo.value) == "Environment loader must have a callable load(); got object"

    def test_it_should_not_import_the_loaders_module(self):
        assert "loaders" not in vars(environments)


class CountingLoader(loaders.MemoryLoader):
    """A ``MemoryLoader`` that records each rulebook name it is asked to load, in order."""

    def __init__(self, sources):
        super().__init__(sources)
        self.loaded: list[str] = []

    def get_source(self, environment, name):
        self.loaded.append(name)
        return super().get_source(environment, name)


def include_rulebook(*names, body="intro:\n  - Hi[.] there.\n"):
    return "include:\n%s\n%s" % ("".join("  - %s\n" % n for n in names), body)


class TestIncludeOrder:
    """FR-010 / R1: cycles are allowed, each rulebook loads once, breadth-first."""

    def test_it_should_compile_a_two_rulebook_cycle_once_each(self):
        loader = CountingLoader({"A": include_rulebook("B"), "B": include_rulebook("A")})
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B"]

    def test_it_should_compile_a_three_rulebook_cycle_once_each_in_order(self):
        loader = CountingLoader(
            {"A": include_rulebook("B"), "B": include_rulebook("C"), "C": include_rulebook("A")},
        )
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B", "C"]

    def test_it_should_load_breadth_first(self):
        loader = CountingLoader(
            {
                "A": include_rulebook("B", "C"),
                "B": include_rulebook("D"),
                "C": "intro:\n  - Hi[.] there.\n",
                "D": "intro:\n  - Hi[.] there.\n",
            },
        )
        environments.Environment(loader=loader, initializing_name="A").load()
        assert loader.loaded == ["A", "B", "C", "D"]

    def test_it_should_concatenate_givens_in_load_order_so_later_values_win(self):
        loader = CountingLoader(
            {
                "A": "include:\n  - B\ngiven:\n  - Mood = 1\nintro:\n  - Hi[.] there.\n",
                "B": "given:\n  - Mood = 2\nintro:\n  - Hi[.] there.\n",
            },
        )
        rulebook = environments.Environment(loader=loader, initializing_name="A").load()
        state = start(Story.from_rulebook(rulebook)).state
        assert state.qualities.get("Mood") == 2


def _nested_choice_source(depth):
    lines = ["rule:"]
    column = 2
    for _ in range(depth):
        lines.append(" " * column + "- choice:")
        column += 4
        lines.append(" " * column + "- Intro.")
    return "\n".join(lines) + "\n"


class TestSourceNestingDepth:
    def test_it_should_count_indentation_levels_ignoring_blanks_and_comments(self):
        source = "a:\n\n  # comment\n  - b:\n      - c\n  - d\n"
        assert environments._source_nesting_depth(source) == 3

    def test_it_should_raise_parse_error_naming_the_rulebook_for_deep_nesting(self, env):
        source = _nested_choice_source(1000)

        with pytest.raises(exceptions.ParseError, match="'deep'.*maximum supported is 128"):
            env.compile_rulebook(source, "deep")

    def test_it_should_raise_parse_error_from_environment_load_via_memory_source(self):
        with pytest.raises(exceptions.ParseError, match="'begin'"):
            MemoryStorySource({"begin": _nested_choice_source(300)}).load()

    @pytest.mark.parametrize(
        ("source", "syml_error", "message"),
        [
            ("r:\n\t- hi\n", syml.exceptions.TabIndentationError, "begin:2:0: A tab character"),
            ("a: 1\na: 2\n", syml.exceptions.DuplicateKeyError, "begin:2:0: Duplicate key 'a'"),
            ("a:\n  b\n c\n", syml.exceptions.OutOfContextNodeError, "begin:3:1: Line 3"),
        ],
    )
    def test_it_should_wrap_syml_syntax_errors_as_parse_error(self, source, syml_error, message):
        with pytest.raises(exceptions.ParseError, match=message) as excinfo:
            MemoryStorySource({"begin": source}).load()

        assert isinstance(excinfo.value.__cause__, syml_error)

    @pytest.mark.parametrize(
        ("source", "message"),
        [
            ("", "A rulebook must be a mapping"),
            ("# c", "A rulebook must be a mapping"),
            ("hello", "A rulebook must be a mapping"),
            ("- a", "A rulebook must be a mapping"),
            ("foo: bar", "Rule .*foo.* must be a non-empty list"),
            ("foo:", "Rule .*foo.* must be a non-empty list"),
            ("foo:\n    a: b", "Rule .*foo.* must be a non-empty list"),
            ("foo:\n    a: a: hi", "Rule .*foo.* must be a non-empty list"),
            ("about: x", "`about` must be a mapping"),
            ("about:\n    - a", "`about` must be a mapping"),
        ],
    )
    def test_it_should_raise_parse_error_for_badly_shaped_rulebooks(self, source, message):
        with pytest.raises(exceptions.ParseError, match=message):
            MemoryStorySource({"begin": source}).load()

    def test_it_should_accept_nesting_at_the_limit(self, env):
        source = "a:\n" + "".join(" " * (i + 1) + "b:\n" for i in range(environments.MAX_SOURCE_NESTING_DEPTH - 1))
        assert environments._source_nesting_depth(source) == environments.MAX_SOURCE_NESTING_DEPTH

    def test_it_should_convert_a_syml_recursion_error_to_parse_error(self, env, monkeypatch):
        def explode(*args, **kwargs):
            raise RecursionError

        monkeypatch.setattr(environments.syml.parsers, "parse", explode)

        with pytest.raises(exceptions.ParseError, match="'x' is nested too deeply"):
            env.compile_rulebook("a: b\n", "x")

    def test_it_should_label_an_unnamed_rulebook(self, env, monkeypatch):
        monkeypatch.setattr(environments.syml.parsers, "parse", lambda *a, **k: (_ for _ in ()).throw(RecursionError()))

        with pytest.raises(exceptions.ParseError, match="<rulebook>"):
            env.compile_rulebook("a: b\n")
