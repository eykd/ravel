"""Unit tests for the compiled ``Story``."""

import pytest

from ravel import types
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


@pytest.fixture
def cloak_path(examples_path):
    return examples_path / "cloak"


@pytest.fixture
def cloak(cloak_path):
    return load_story(cloak_path)


def rulebook_with(concept, locations, givens=()):
    return {
        "metadata": {},
        "rulebook": {concept: {"rules": [], "locations": locations}},
        "givens": list(givens),
    }


class TestFromRulebook:
    def test_it_keeps_the_rulebook(self, cloak_env):
        rulebook = cloak_env.load()
        assert Story.from_rulebook(rulebook).rulebook is rulebook


class TestSituation:
    def test_it_returns_the_situation_at_a_location(self, cloak):
        situation = cloak.situation("begin::intro")
        assert isinstance(situation, types.Situation)
        assert situation is cloak.rulebook["rulebook"]["Situation"]["locations"]["begin::intro"]

    def test_it_raises_key_error_for_an_unknown_location(self, cloak):
        with pytest.raises(KeyError):
            cloak.situation("begin::nowhere")

    def test_it_raises_key_error_for_a_non_situation_location(self):
        story = Story.from_rulebook(rulebook_with("Situation", {"notes::aside": ["just", "strings"]}))
        with pytest.raises(KeyError):
            story.situation("notes::aside")

    def test_it_raises_key_error_for_another_concepts_location(self):
        story = Story.from_rulebook(rulebook_with("Note", {"notes::aside": ["just", "strings"]}))
        with pytest.raises(KeyError):
            story.situation("notes::aside")


class TestHasLocation:
    def test_it_is_true_for_a_situation(self, cloak):
        assert cloak.has_location("foyer::foyer")

    def test_it_is_false_for_an_unknown_location(self, cloak):
        assert not cloak.has_location("foyer::nowhere")

    def test_it_is_false_for_a_non_situation_location(self):
        story = Story.from_rulebook(rulebook_with("Situation", {"notes::aside": ["just", "strings"]}))
        assert not story.has_location("notes::aside")


class TestGivens:
    def test_they_are_the_rulebook_givens_as_a_tuple(self, cloak):
        assert cloak.givens == tuple(cloak.rulebook["givens"])
