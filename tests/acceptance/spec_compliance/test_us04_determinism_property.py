"""US4-AS4: two plays of the same story with the same choice indices are identical.

Property test pinning FR-015. Every choice is drawn from the menu the engine actually offered at
that step (an index into the current ``ChoicesOffered``), never a made-up location string.
"""

from pathlib import Path
from typing import Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ravel import engine
from ravel.adapters.story_source import MemoryStorySource
from ravel.app.saves import encode_save
from ravel.engine.outputs import ChoicesOffered, Output
from ravel.engine.state import GameState
from ravel.engine.story import Story
from tests.helpers import strict_conditions

pytestmark = pytest.mark.acceptance

CLOAK: Final = Path(__file__).resolve().parents[3] / "examples" / "cloak"
SOURCES: Final = {path.stem: path.read_text(encoding="utf-8") for path in sorted(CLOAK.glob("*.ravel"))}

Trace = list[tuple[tuple[Output, ...], GameState, bytes]]


def play(story: Story, picks: list[int]) -> Trace:
    """Play ``story`` taking ``offered[pick % len(offered)]`` per index; stop at a halt or when picks run out."""
    step = engine.start(story)
    trace: Trace = [(step.outputs, step.state, encode_save(story, step.state))]
    for pick in picks:
        menus = [output for output in step.outputs if isinstance(output, ChoicesOffered)]
        if not menus:
            break
        choices = menus[-1].choices
        step = engine.choose(story, step.state, choices[pick % len(choices)].location)
        trace.append((step.outputs, step.state, encode_save(story, step.state)))
    return trace


@settings(max_examples=200, deadline=None, derandomize=True, database=None)
@given(st.lists(st.integers(min_value=0), max_size=30))
def test_us4_as4_same_choice_indices_give_identical_outputs_states_and_saves(picks: list[int]) -> None:
    """US4-AS4: compiling Cloak twice and playing the same indices yields equal outputs, states and save bytes."""
    with strict_conditions():
        first = play(MemoryStorySource(SOURCES).load(), picks)
        second = play(MemoryStorySource(SOURCES).load(), picks)

    assert len(first) == len(second)
    for (outputs_a, state_a, bytes_a), (outputs_b, state_b, bytes_b) in zip(first, second, strict=True):
        assert outputs_a == outputs_b
        assert state_a == state_b
        assert bytes_a == bytes_b
