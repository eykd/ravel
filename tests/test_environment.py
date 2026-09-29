from unittest.mock import patch

import pytest

from ravel import environments, exceptions, loaders
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
