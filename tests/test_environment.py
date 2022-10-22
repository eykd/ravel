from unittest.mock import patch

import pytest

from ravel import environments, loaders


@pytest.fixture
def env(examples_path):
    return environments.Environment(
        loader=loaders.FileSystemLoader(base_path=examples_path / "simple"),
    )


class TestGetRulebook:
    def test_it_should_load_the_rulebook_and_its_includes(self, env):
        rulebook = env.load()
        assert "begin::intro" in rulebook.concepts["Situation"].locations
        assert "rooms::rooms" in rulebook.concepts["Situation"].locations
        assert "actions::actions" in rulebook.concepts["Situation"].locations

        new_rulebook = env.load()
        assert new_rulebook == rulebook
