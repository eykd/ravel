"""Unit tests for ``choose``: preconditions, then the run loop's directive dispatch."""

from pathlib import Path

import pytest

from ravel import types
from ravel.engine.engine import choose, start
from ravel.engine.errors import GameOverError, InvalidStateError, NotOfferedError, NotWaitingError
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    QualityChanged,
    SituationEntered,
    SituationExited,
    TextShown,
)
from ravel.engine.state import Frame, GameState, Outcome, Qualities, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stories"


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


def hand_built_story(directives):
    """A one-situation story at location ``"s"`` holding ``directives``, bypassing the compiler."""
    rulebook: types.CompiledRulebook = {
        "metadata": {},
        "rulebook": {
            "Situation": {
                "rules": [types.Rule("s", [])],
                "locations": {"s": types.Situation(intro=types.Text("S"), directives=directives)},
            }
        },
        "givens": [],
    }
    return Story(rulebook=rulebook, identity="sha256:hand-built", end_labels=frozenset())


def waiting(offered, stack=(), qualities=None):
    return GameState(
        qualities=qualities if qualities is not None else Qualities(),
        stack=stack,
        status=Status.WAITING,
        offered=offered,
        outcome=None,
    )


class Unknown:
    """A directive type the run loop has no handler for."""


@pytest.fixture
def mini():
    return load_story(FIXTURES / "mini")


@pytest.fixture
def s0(mini):
    return start(mini).state


# --- Preconditions -------------------------------------------------------------------------


def test_choose_on_a_halted_game_raises_game_over(mini):
    state = GameState(qualities=Qualities(), stack=(), status=Status.HALTED, offered=(), outcome=Outcome("won"))
    snapshot = GameState(qualities=Qualities(), stack=(), status=Status.HALTED, offered=(), outcome=Outcome("won"))

    with pytest.raises(GameOverError, match=r"^the game is over \(outcome: 'won'\)$"):
        choose(mini, state, "begin::fork")

    assert state == snapshot


def test_game_over_is_checked_before_waiting_and_offered(mini):
    state = GameState(qualities=Qualities(), stack=(), status=Status.HALTED, offered=(), outcome=Outcome("won"))

    with pytest.raises(GameOverError):
        choose(mini, state, "begin::nowhere")


def test_choose_on_a_running_state_raises_not_waiting(mini):
    state = GameState(qualities=Qualities(), stack=(), status=Status.RUNNING, offered=(), outcome=None)
    snapshot = GameState(qualities=Qualities(), stack=(), status=Status.RUNNING, offered=(), outcome=None)

    with pytest.raises(NotWaitingError):
        choose(mini, state, "begin::nowhere")

    assert state == snapshot


def test_choose_an_unoffered_location_raises_not_offered(mini, s0):
    snapshot = start(mini).state

    with pytest.raises(NotOfferedError, match=r"^'begin::dead-end' is not an offered choice; offered: "):
        choose(mini, s0, "begin::dead-end")

    assert s0 == snapshot


# --- Gather example (US2-AS3) --------------------------------------------------------------


def test_choosing_fork_runs_to_its_choice_block(mini, s0):
    s1 = choose(mini, s0, "begin::fork")

    assert s1.outputs == (
        SituationEntered("begin::fork"),
        TextShown("You stand at a fork."),
        ChoicesOffered(
            (
                ChoiceOption("begin::fork::go-left", "Go left"),
                ChoiceOption("begin::fork::go-right", "Go right"),
            )
        ),
    )


def test_choice_block_rests_on_get_choice_without_running_the_gather(mini, s0):
    s1 = choose(mini, s0, "begin::fork")

    assert s1.state.stack == (Frame("begin::fork", 4),)
    assert s1.state.status is Status.WAITING
    assert s1.state.offered == ("begin::fork::go-left", "begin::fork::go-right")
    assert s1.state.qualities.get("Place") is None


def test_gather_runs_only_after_the_chosen_sub_situation_finishes(mini, s0):
    s1 = choose(mini, s0, "begin::fork")
    s2 = choose(mini, s1.state, "begin::fork::go-left")

    assert s2.outputs[:6] == (
        SituationEntered("begin::fork::go-left"),
        TextShown("You go left."),
        SituationExited("begin::fork::go-left"),
        TextShown("The road rejoins."),
        QualityChanged("Place", None, "Middle"),
        SituationExited("begin::fork"),
    )
    assert s2.state.stack == ()
    assert s2.state.qualities.get("Place") == "Middle"


# --- Unconditional pop ---------------------------------------------------------------------


def test_situation_pops_unconditionally_past_its_last_directive(mini, s0):
    step = choose(mini, s0, "begin::bridge")

    assert step.outputs[:3] == (
        SituationEntered("begin::bridge"),
        TextShown("You cross the bridge."),
        SituationExited("begin::bridge"),
    )
    assert step.state.stack == ()
    assert isinstance(step.outputs[-1], ChoicesOffered)
    assert step.state.status is Status.WAITING


# --- Text dispatch -------------------------------------------------------------------------


def test_blank_and_unmet_text_is_not_shown():
    unmet = types.Predicate("Seen", types.Comparison("Seen", "=", 1))
    story = hand_built_story(
        [
            types.Text("   "),
            types.Text("Hidden.", predicate=unmet),
            types.Text("Shown.", sticky=True),
        ]
    )

    step = choose(story, waiting(("s",)), "s")

    assert step.outputs[:3] == (
        SituationEntered("s"),
        TextShown("Shown.", sticky=True),
        SituationExited("s"),
    )


# --- InvalidStateError from hand-built states ----------------------------------------------


def test_unknown_directive_raises_invalid_state():
    story = hand_built_story([types.Text("hi"), Unknown()])

    with pytest.raises(InvalidStateError):
        choose(story, waiting(("s",)), "s")


def test_choice_reached_directly_raises_invalid_state():
    story = hand_built_story([types.Choice("s::x")])

    with pytest.raises(InvalidStateError):
        choose(story, waiting(("s",)), "s")


def test_get_choice_reached_directly_raises_invalid_state():
    story = hand_built_story([types.GetChoice()])

    with pytest.raises(InvalidStateError):
        choose(story, waiting(("s",)), "s")


def test_unknown_location_raises_invalid_state(mini):
    with pytest.raises(InvalidStateError):
        choose(mini, waiting(("begin::nowhere",)), "begin::nowhere")


def test_out_of_range_ip_raises_invalid_state(mini):
    # The parent's resting ip is not on a GetChoice; resuming it lands at ip -1.
    state = waiting(("begin::fork::go-left",), stack=(Frame("begin::fork", -2),))

    with pytest.raises(InvalidStateError):
        choose(mini, state, "begin::fork::go-left")
