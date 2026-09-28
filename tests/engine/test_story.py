"""Unit tests for the compiled ``Story`` and its stable content identity."""

import os
import re
import shutil
import subprocess
import sys

import pytest

from ravel import types
from ravel.engine.story import IR_VERSION, Story, fingerprint
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

IDENTITY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

IDENTITY_SCRIPT = """
import sys
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader
env = Environment(loader=FileSystemLoader(base_path=sys.argv[1]))
print(Story.from_rulebook(env.load()).identity)
"""


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


def edit(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def identity_under_hash_seed(path, seed):
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", IDENTITY_SCRIPT, str(path)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def cloak_path(examples_path):
    return examples_path / "cloak"


@pytest.fixture
def cloak_copy(cloak_path, tmp_path):
    """A copy of Cloak in a different absolute directory, free to edit."""
    target = tmp_path / "elsewhere" / "cloak"
    shutil.copytree(cloak_path, target)
    return target


@pytest.fixture
def cloak(cloak_path):
    return load_story(cloak_path)


def rulebook_with(concept, locations, givens=()):
    return {
        "metadata": {},
        "rulebook": {concept: {"rules": [], "locations": locations}},
        "givens": list(givens),
    }


class TestIrVersion:
    def test_it_is_one(self):
        assert IR_VERSION == 1


class TestFromRulebook:
    def test_identity_is_a_sha256_digest(self, cloak):
        assert IDENTITY_RE.match(cloak.identity)

    def test_identity_is_the_rulebook_fingerprint(self, cloak_env):
        rulebook = cloak_env.load()
        assert Story.from_rulebook(rulebook).identity == fingerprint(rulebook)

    def test_it_keeps_the_rulebook(self, cloak_env):
        rulebook = cloak_env.load()
        assert Story.from_rulebook(rulebook).rulebook is rulebook

    def test_cloak_has_the_win_and_loss_end_labels(self, cloak):
        assert cloak.end_labels == frozenset({"won", "lost"})


class TestIdentityStability:
    def test_it_is_the_same_from_a_different_absolute_directory(self, cloak, cloak_copy):
        assert load_story(cloak_copy).identity == cloak.identity

    def test_it_is_the_same_across_a_whitespace_and_comment_only_edit(self, cloak, cloak_copy):
        foyer = cloak_copy / "foyer.ravel"
        edit(foyer, "\n\noutside:", "\n\n\n# The view out the front doors.\n\noutside:")
        foyer.write_text("# The foyer of the Opera House.\n\n" + foyer.read_text() + "\n\n")
        assert load_story(cloak_copy).identity == cloak.identity

    def test_it_is_the_same_under_different_hash_seeds(self, cloak, cloak_path):
        seed_zero = identity_under_hash_seed(cloak_path, "0")
        seed_one = identity_under_hash_seed(cloak_path, "1")
        assert seed_zero == seed_one == cloak.identity

    def test_it_is_the_same_for_two_independent_loads(self, cloak, cloak_path):
        assert load_story(cloak_path) == cloak


class TestIdentitySensitivity:
    def test_it_changes_on_a_one_character_text_edit(self, cloak, cloak_copy):
        edit(cloak_copy / "foyer.ravel", "spacious hall", "spacious halls")
        assert load_story(cloak_copy).identity != cloak.identity

    def test_it_changes_when_a_given_changes(self, cloak, cloak_copy):
        edit(cloak_copy / "begin.ravel", '"Wearing Cloak" = 1', '"Wearing Cloak" = 2')
        assert load_story(cloak_copy).identity != cloak.identity

    def test_it_ignores_metadata(self, cloak_env):
        rulebook = cloak_env.load()
        before = fingerprint(rulebook)
        rulebook["metadata"] = {"title": "The Cloak of Darkness"}
        assert fingerprint(rulebook) == before


class TestFingerprint:
    def test_it_refuses_a_set(self):
        rulebook = rulebook_with("Situation", {}, givens=[types.Operation("q", "=", {1, 2})])
        with pytest.raises(TypeError):
            fingerprint(rulebook)

    def test_it_refuses_a_mapping_with_a_non_str_key(self):
        rulebook = rulebook_with("Situation", {}, givens=[types.Operation("q", "=", {1: 2})])
        with pytest.raises(TypeError):
            fingerprint(rulebook)

    def test_it_refuses_a_source_position(self):
        position = types.Pos(index=0, line=1, column=1)
        source = types.Source(filename="/abs/path/story.ravel", start=position, end=position, text="x")
        rulebook = rulebook_with("Situation", {}, givens=[types.Operation("q", "=", source)])
        with pytest.raises(TypeError):
            fingerprint(rulebook)

    def test_it_encodes_the_value_sentinel(self):
        rulebook = rulebook_with("Situation", {}, givens=[types.Operation("q", "+=", types.VALUE)])
        assert IDENTITY_RE.match(fingerprint(rulebook))


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
