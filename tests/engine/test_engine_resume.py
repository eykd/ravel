"""Unit tests for ``engine.present`` and ``engine.resume`` (contracts/engine-api.md, 2026-09-28).

``resume`` turns a story-free ``SavedGame`` into a ``Step`` against a (possibly changed) story,
never raising: a stale frame is truncated instead. Built from hand-constructed stories and
``SavedGame``s so every branch (halted, unknown location, no matching block, out-of-range
ordinal, resolved-empty requery, resolved-empty dead end) is directly reachable.
"""

from pathlib import Path

import pytest

from ravel.engine.engine import choose, present, resume, start
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, Halted, StoryChanged
from ravel.engine.state import Anchor, GameState, Outcome, Qualities, SavedFrame, SavedGame, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stories"


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


@pytest.fixture
def mini():
    return load_story(FIXTURES / "mini")


@pytest.fixture
def duplicate_blocks():
    return load_story(FIXTURES / "duplicate-blocks")


# --- present -----------------------------------------------------------------------------------


def test_present_rederives_menu_labels_for_a_waiting_state(mini):
    state = start(mini).state  # waiting at the top-level query menu (Location = "Fork")

    assert present(mini, state) == (
        ChoicesOffered(
            (
                ChoiceOption("begin::crossroads", "Study the signpost"),
                ChoiceOption("begin::fork", "You stand at a fork."),
                ChoiceOption("begin::bridge", "Cross the bridge"),
            )
        ),
    )


def test_present_emits_halted_with_the_outcome(mini):
    state = GameState(qualities=Qualities(), stack=(), status=Status.HALTED, offered=(), outcome=Outcome("won", False))

    assert present(mini, state) == (Halted("won", False),)


def test_present_emits_halted_with_empty_label_when_outcome_is_none():
    empty_story = Story(rulebook={"metadata": {}, "rulebook": {}, "givens": []})
    state = GameState(qualities=Qualities(), stack=(), status=Status.HALTED, offered=(), outcome=None)

    assert present(empty_story, state) == (Halted("", False),)


# --- resume: halted ------------------------------------------------------------------------


def test_resume_restores_a_halted_save_verbatim(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Fork"}),
        stack=(),
        status=Status.HALTED,
        outcome=Outcome("won", False),
    )

    step = resume(mini, saved)

    assert step.outputs == (Halted("won", False),)
    assert step.state.status is Status.HALTED
    assert step.state.stack == ()
    assert step.state.offered == ()
    assert step.state.outcome == Outcome("won", False)
    assert step.state.qualities == saved.qualities


# --- resume: waiting, unchanged story --------------------------------------------------------


def test_resume_round_trips_a_waiting_save_against_an_unchanged_story(mini):
    step = start(mini)
    step = choose(mini, step.state, "begin::bridge")
    step = choose(mini, step.state, "begin::bridge::follow-the-tunnel")
    state = step.state

    saved = SavedGame(
        qualities=state.qualities,
        stack=(
            SavedFrame(
                location="begin::bridge",
                anchor=Anchor(
                    choices=("begin::bridge::follow-the-tunnel", "begin::bridge::shout-into-the-void"), ordinal=0
                ),
            ),
            SavedFrame(
                location="begin::bridge::follow-the-tunnel",
                anchor=Anchor(
                    choices=(
                        "begin::bridge::follow-the-tunnel::press-onward-into-the-dark",
                        "begin::bridge::follow-the-tunnel::turn-back-to-the-bridge",
                    ),
                    ordinal=0,
                ),
            ),
        ),
        status=Status.WAITING,
        outcome=None,
    )

    resumed = resume(mini, saved)

    assert resumed.state == state
    assert resumed.outputs == present(mini, state)
    assert not any(isinstance(output, StoryChanged) for output in resumed.outputs)


# --- resume: truncation branches ------------------------------------------------------------


def test_resume_truncates_a_frame_whose_location_no_longer_exists(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Fork"}),
        stack=(SavedFrame(location="begin::gone", anchor=Anchor(choices=("x",), ordinal=0)),),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(mini, saved)

    assert step.outputs[0] == StoryChanged(dropped=("begin::gone",))
    assert step.state.stack == ()


def test_resume_truncates_a_frame_whose_anchor_matches_no_block(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Fork"}),
        stack=(SavedFrame(location="begin::fork", anchor=Anchor(choices=("not-a-real-target",), ordinal=0)),),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(mini, saved)

    assert step.outputs[0] == StoryChanged(dropped=("begin::fork",))
    assert step.state.stack == ()


def test_resume_drops_every_frame_above_a_truncated_one(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Fork"}),
        stack=(
            SavedFrame(location="begin::gone", anchor=Anchor(choices=("x",), ordinal=0)),
            SavedFrame(location="begin::also-gone", anchor=Anchor(choices=("y",), ordinal=0)),
        ),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(mini, saved)

    assert step.outputs[0] == StoryChanged(dropped=("begin::gone", "begin::also-gone"))
    assert step.state.stack == ()


def test_resume_uses_the_first_match_when_the_ordinal_is_out_of_range(duplicate_blocks):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Loop"}),
        stack=(SavedFrame(location="begin::loop", anchor=Anchor(choices=("begin::loop::go-on",), ordinal=99)),),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(duplicate_blocks, saved)

    assert not any(isinstance(output, StoryChanged) for output in step.outputs)
    assert step.state.stack[0].location == "begin::loop"
    # Resolved to the first (ordinal 0) matching block, not the last -- its effect ("Visited")
    # has not run yet, exactly as when first reaching this block via a fresh `choose`.
    assert step.state.qualities.get("Visited") is None
    fresh = choose(duplicate_blocks, start(duplicate_blocks).state, "begin::loop")
    assert fresh.state == step.state


# --- resume: resolved stack empty -------------------------------------------------------------


def test_resume_requeries_when_the_saved_stack_was_already_empty(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Fork", "Count": 1}),
        stack=(),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(mini, saved)

    assert not any(isinstance(output, StoryChanged) for output in step.outputs)
    assert isinstance(step.outputs[0], ChoicesOffered)
    assert step.state.status is Status.WAITING


def test_resume_halts_on_a_dead_end_when_the_resolved_stack_is_empty(mini):
    saved = SavedGame(
        qualities=Qualities.from_mapping({"Location": "Never Anywhere"}),
        stack=(),
        status=Status.WAITING,
        outcome=None,
    )

    step = resume(mini, saved)

    assert step.outputs == (Halted("", True),)
    assert step.state.status is Status.HALTED
    assert step.state.outcome == Outcome("", True)
