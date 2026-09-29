"""Unit tests for ``ravel.adapters.story_source.FileSystemStorySource`` (contracts/session-api.md)."""

import pytest

from ravel.adapters.story_source import FileSystemStorySource, MemoryStorySource
from ravel.app.ports import StorySource
from ravel.engine.engine import start
from ravel.engine.story import Story
from ravel.exceptions import ParseError, RulebookNotFound
from ravel.parsers import MAX_EXPRESSION_OPERANDS


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


SRC = "given:\n  - Location = 'Start'\n\nstart:\n  - when:\n      - Location = 'Start'\n  - Ready.\n"


def test_memory_source_compiles_a_story_the_engine_plays():
    source = MemoryStorySource({"begin": SRC})

    story = source.load()

    assert isinstance(story, Story)
    assert start(story).state.qualities.get("Location") == "Start"


def test_memory_source_entry_starts_from_another_rulebook():
    other = "given:\n  - Location = 'Other'\n\nx:\n  - when:\n      - Location = 'Other'\n  - Hi.\n"
    source = MemoryStorySource({"begin": SRC, "other": other}, entry="other")

    story = source.load()

    assert start(story).state.qualities.get("Location") == "Other"


def test_memory_source_each_load_compiles_a_fresh_story():
    source = MemoryStorySource({"begin": SRC})

    a = source.load()
    b = source.load()

    assert a is not b
    assert start(a) == start(b)


def test_memory_source_missing_entry_raises_rulebook_not_found():
    source = MemoryStorySource({"begin": SRC}, entry="nope")

    with pytest.raises(RulebookNotFound):
        source.load()


def test_memory_source_satisfies_the_story_source_port():
    source: StorySource = MemoryStorySource({"begin": SRC})

    assert isinstance(source.load(), Story)


def test_memory_source_rejects_an_over_limit_when_predicate_at_load():
    chain = "+".join(["1"] * (MAX_EXPRESSION_OPERANDS + 1))
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == %s\n  - Ready.\n" % chain

    with pytest.raises(ParseError):
        MemoryStorySource({"begin": src}).load()


def test_memory_source_rejects_an_over_limit_effect_at_load():
    chain = "+".join(["1"] * (MAX_EXPRESSION_OPERANDS + 1))
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == 0\n  - Ready.\n  - effect: X = %s\n" % chain

    with pytest.raises(ParseError):
        MemoryStorySource({"begin": src}).load()


def _nested(depth):
    return "(" * depth + "1" + ")" * depth


def test_memory_source_rejects_deep_parentheses_in_an_effect_at_load():
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == 0\n  - Ready.\n  - effect: X = %s\n" % _nested(300)

    with pytest.raises(ParseError):
        MemoryStorySource({"begin": src}).load()


def test_memory_source_rejects_deep_parentheses_in_a_when_predicate_at_load():
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == %s\n  - Ready.\n" % _nested(300)

    with pytest.raises(ParseError):
        MemoryStorySource({"begin": src}).load()


def test_memory_source_rejects_deep_parentheses_in_a_text_prefix_at_load():
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == 0\n  - Ready.\n  - {X == %s}More.\n" % _nested(300)

    with pytest.raises(ParseError):
        MemoryStorySource({"begin": src}).load()


def test_memory_source_accepts_modest_parenthesis_nesting():
    src = "given:\n  - X = 0\n\nstart:\n  - when:\n      - X == 0\n  - Ready.\n  - effect: X = %s\n" % _nested(5)

    assert isinstance(MemoryStorySource({"begin": src}).load(), Story)
