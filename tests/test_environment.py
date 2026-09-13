from unittest.mock import patch

import pytest

from ravel import environments, exceptions, loaders


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
