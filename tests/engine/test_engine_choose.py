"""Unit tests for ``choose``: preconditions, then the run loop's directive dispatch."""

from pathlib import Path

import pytest

from ravel import types
from ravel.engine.engine import choose, start
from ravel.engine.errors import (
    EngineError,
    GameOverError,
    InvalidOperationError,
    InvalidStateError,
    NotOfferedError,
    NotWaitingError,
)
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
from ravel.exceptions import EvaluationError
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
    return Story(rulebook=rulebook)


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


def test_a_second_choice_block_in_one_situation_is_found_after_the_first_doesnt_match():
    """A situation with two separate choice blocks (data-model.md SS Choice blocks): resuming at
    the second exercises ``begin_choices``'s scan past a first, non-matching block."""
    duplicate = load_story(FIXTURES / "duplicate-blocks")
    s0 = start(duplicate).state
    s1 = choose(duplicate, s0, "begin::loop")

    s2 = choose(duplicate, s1.state, "begin::loop::go-on")

    assert s2.state.stack == (Frame("begin::loop", 7),)
    assert s2.state.offered == ("begin::loop::go-on",)
    assert s2.state.qualities.get("Visited") == 1


# --- Unconditional pop ---------------------------------------------------------------------


def test_situation_pops_unconditionally_past_its_last_directive(mini, s0):
    step = choose(mini, s0, "begin::crossroads")

    assert step.outputs[:3] == (
        SituationEntered("begin::crossroads"),
        TextShown("The signpost points every which way."),
        SituationExited("begin::crossroads"),
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


def test_choice_block_running_off_the_end_raises_invalid_state():
    story = hand_built_story([types.BeginChoices(), types.Choice("s")])

    with pytest.raises(InvalidStateError):
        choose(story, waiting(("s",)), "s")


def test_choice_block_without_get_choice_raises_invalid_state():
    story = hand_built_story([types.BeginChoices(), types.Choice("s"), types.Text("stray")])

    with pytest.raises(InvalidStateError):
        choose(story, waiting(("s",)), "s")


# --- Unevaluable operations (RT-1, RT-2) ---------------------------------------------------


def test_effect_dividing_by_an_unset_quality_raises_invalid_operation():
    story = hand_built_story(
        [types.Operation("X", "=", types.Expression(10, "/", types.QualityRef("Zero")))],
    )

    with pytest.raises(InvalidOperationError) as excinfo:
        choose(story, waiting(("s",)), "s")

    assert isinstance(excinfo.value, EngineError)
    assert isinstance(excinfo.value.__cause__, EvaluationError)
    assert isinstance(excinfo.value.__cause__.__cause__, ZeroDivisionError)


def test_effect_adding_a_number_to_a_string_quality_raises_invalid_operation():
    story = hand_built_story(
        [types.Operation("X", "=", types.Expression(types.QualityRef("Name"), "+", 1))],
    )
    state = waiting(("s",), qualities=Qualities().set("Name", "a"))

    with pytest.raises(InvalidOperationError) as excinfo:
        choose(story, state, "s")

    assert isinstance(excinfo.value.__cause__, EvaluationError)
    assert isinstance(excinfo.value.__cause__.__cause__, TypeError)


def test_effect_reading_a_set_quality_stores_the_computed_value():
    story = hand_built_story(
        [types.Operation("X", "=", types.Expression(types.QualityRef("Base"), "+", 1))],
    )
    state = waiting(("s",), qualities=Qualities().set("Base", 4))

    step = choose(story, state, "s")

    assert step.state.qualities.get("X") == 5


def test_text_prefix_that_cannot_evaluate_hides_its_line_and_play_continues():
    unevaluable = types.Comparison("Name", "==", types.Expression(1, "/", types.QualityRef("Zero")))
    story = hand_built_story(
        [
            types.Text("hidden", predicate=types.Predicate("p", unevaluable)),
            types.Text("shown"),
        ],
    )

    step = choose(story, waiting(("s",)), "s")

    assert TextShown("hidden", False) not in step.outputs
    assert TextShown("shown", False) in step.outputs
