"""Acceptance test for US3 (specs/002-spec-compliance): rulebooks compile the way the spec describes.

RED per ravel-h6v.5.4.1 -- expected to FAIL until the US3 Green leaves land. Plain pytest (PD-15):
drives the public environment, loader and engine surfaces and asserts computed values AND kinds.
"""

from typing import Any

import pytest

from ravel import engine
from ravel.engine.outputs import (
    ChoicesOffered,
    Output,
    QualityChanged,
    SituationEntered,
    SituationExited,
    TextShown,
)
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.exceptions import ParseError
from ravel.loaders import MemoryLoader
from ravel.types import Rule, Text

pytestmark = pytest.mark.acceptance


class CountingLoader(MemoryLoader):
    """A ``MemoryLoader`` that records the name of every rulebook it is asked to load."""

    def __init__(self, sources: dict[str, str]) -> None:
        super().__init__(sources)
        self.loaded: list[str] = []

    def load(self, environment: Any, name: Any) -> Any:
        self.loaded.append(name)
        return super().load(environment, name)


def compile_story(source: str) -> Story:
    """Compile a single ``begin`` rulebook into a ``Story``."""
    return Story.from_rulebook(Environment(loader=MemoryLoader({"begin": source})).load())


def include_loader(graph: dict[str, list[str]]) -> CountingLoader:
    """Build a counting loader whose rulebooks include the names listed for them in ``graph``."""
    sources = {}
    for name, includes in graph.items():
        text = ""
        if includes:
            text += "include:\n" + "".join(f"  - {other}\n" for other in includes)
        text += f"{name}_situation:\n  - Intro of {name}.\n"
        sources[name] = text
    return CountingLoader(sources)


def texts(outputs: tuple[Output, ...]) -> list[str]:
    return [output.text for output in outputs if isinstance(output, TextShown)]


def last_menu(outputs: tuple[Output, ...]) -> ChoicesOffered:
    return [output for output in outputs if isinstance(output, ChoicesOffered)][-1]


def test_us3_as1_situation_first_item_declares_a_situation_concept_not_intro_text() -> None:
    """US3-AS1: a rule whose first item is the word ``Situation`` and has no ``when:`` is a Situation concept."""
    source = "declared:\n  - Situation\n  - You are here[.], somewhere.\n"

    rulebook = Environment(loader=MemoryLoader({"begin": source})).load()

    assert list(rulebook["rulebook"]) == ["Situation"]
    assert rulebook["rulebook"]["Situation"]["rules"] == [Rule("begin::declared", [])]
    assert rulebook["rulebook"]["Situation"]["locations"]["begin::declared"].intro == Text("You are here.")


def test_us3_as2_unregistered_one_word_first_line_is_intro_text() -> None:
    """US3-AS2: a one-word first line that is not a registered concept (``Hello``) is intro text."""
    source = "lonely:\n  - Hello\n  - There you are.\n"

    rulebook = Environment(loader=MemoryLoader({"begin": source})).load()

    assert list(rulebook["rulebook"]) == ["Situation"]
    assert rulebook["rulebook"]["Situation"]["locations"]["begin::lonely"].intro == Text("Hello")


@pytest.mark.parametrize(
    ("graph", "expected"),
    [
        ({"begin": ["other"], "other": ["begin"]}, ["begin", "other"]),
        ({"begin": ["b"], "b": ["c"], "c": ["begin"]}, ["begin", "b", "c"]),
        ({"begin": ["b", "c"], "b": ["d"], "c": [], "d": []}, ["begin", "b", "c", "d"]),
    ],
)
def test_us3_as3_includes_compile_each_rulebook_once_breadth_first(
    graph: dict[str, list[str]], expected: list[str]
) -> None:
    """US3-AS3: mutually-including rulebooks each compile exactly once, breadth-first, and loading ends."""
    loader = include_loader(graph)

    Environment(loader=loader).load()

    assert loader.loaded == expected


def test_us3_as4_choice_text_shows_after_the_choice_line_and_the_menu_label_is_unchanged() -> None:
    """US3-AS4 (i): ``text:`` in a ``choice:`` is shown after the choice's own text; the label stays ``Go``."""
    story = compile_story(
        "intro:\n  - Begin.\n  - choice:\n      - [Go]You go.\n      - text: Extra words.\n      - effect: X += 1\n"
    )
    step = engine.start(story)
    step = engine.choose(story, step.state, last_menu(step.outputs).choices[0].location)
    menu = last_menu(step.outputs)
    assert [c.label for c in menu.choices] == ["Go"]
    step = engine.choose(story, step.state, menu.choices[0].location)

    assert texts(step.outputs) == ["You go.", "Extra words."]
    assert [o for o in step.outputs if isinstance(o, QualityChanged)] == [QualityChanged("X", None, 1)]
    assert [o for o in step.outputs if isinstance(o, (SituationEntered, SituationExited))] == [
        SituationEntered("begin::intro::go"),
        SituationExited("begin::intro::go"),
        SituationExited("begin::intro"),
    ]


def test_us3_as4_effect_before_text_runs_in_document_order() -> None:
    """US3-AS4 (ii): a ``text:`` listed after ``effect:`` sees the effect's result."""
    story = compile_story(
        "intro:\n"
        "  - Begin.\n"
        "  - choice:\n"
        "      - [Go]You go.\n"
        "      - effect: X += 1\n"
        "      - text: {X == 1}After effect.\n"
    )
    step = engine.start(story)
    step = engine.choose(story, step.state, last_menu(step.outputs).choices[0].location)
    step = engine.choose(story, step.state, last_menu(step.outputs).choices[0].location)

    assert texts(step.outputs) == ["You go.", "After effect."]


def test_us3_rt5_text_before_the_choice_line_fails_with_a_positioned_parse_error() -> None:
    """US3-RT-5: ``text:`` before the ``[Go]`` line is a ParseError naming the source position."""
    source = "intro:\n  - Begin.\n  - choice:\n      - text: Extra words.\n      - [Go]You go.\n"

    with pytest.raises(ParseError, match=r"Line \d+, Column \d+"):
        Environment(loader=MemoryLoader({"begin": source})).load()
