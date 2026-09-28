"""Unit tests for ``ravel.adapters.story_source.FileSystemStorySource`` (contracts/session-api.md)."""

import pytest

from ravel.adapters.story_source import FileSystemStorySource
from ravel.engine.engine import start
from ravel.engine.story import Story
from ravel.exceptions import RulebookNotFound


def test_it_loads_a_compiled_story_from_a_path_directory(examples_path):
    source = FileSystemStorySource(examples_path / "cloak")

    story = source.load()

    assert isinstance(story, Story)
    step = start(story)
    assert step.state.qualities.get("Location") == "Intro"


def test_it_accepts_a_str_path_too(examples_path):
    source = FileSystemStorySource(str(examples_path / "cloak"))

    story = source.load()

    assert isinstance(story, Story)


def test_it_propagates_a_missing_rulebook_error(tmp_path):
    source = FileSystemStorySource(tmp_path)

    with pytest.raises(RulebookNotFound):
        source.load()


def test_each_load_call_recompiles_a_fresh_story(examples_path):
    source = FileSystemStorySource(examples_path / "cloak")

    a = source.load()
    b = source.load()

    assert a is not b
    # Recompiling produces functionally equivalent stories: the same first step.
    assert start(a) == start(b)
