"""Unit tests for query mode: menu order, the dead end, determinism, and isolation between games."""

from pathlib import Path

import pytest

from ravel.engine.engine import choose, start
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, Halted, QualityChanged, SituationExited
from ravel.engine.state import Outcome, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stories"


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


@pytest.fixture
def menu():
    return load_story(FIXTURES / "menu")


@pytest.fixture
def mini():
    return load_story(FIXTURES / "mini")


@pytest.fixture
def cloak(examples_path):
    return load_story(examples_path / "cloak")


# --- Menu order (FR-011) -------------------------------------------------------------------


def test_query_mode_orders_by_predicate_count_then_location_descending(menu):
    step = start(menu)

    assert step.state.offered == ("begin::bravo", "begin::mike", "begin::zulu", "begin::alpha")


def test_query_mode_offers_each_match_with_its_intro_text(menu):
    step = start(menu)

    assert step.outputs[-1] == ChoicesOffered(
        (
            ChoiceOption("begin::bravo", "Bravo"),
            ChoiceOption("begin::mike", "Mike"),
            ChoiceOption("begin::zulu", "Zulu"),
            ChoiceOption("begin::alpha", "Alpha"),
        )
    )


def test_mini_query_mode_puts_the_most_specific_match_first(mini):
    step = start(mini)

    assert step.state.offered == ("begin::crossroads", "begin::fork", "begin::bridge")


# --- Dead end (FR-012) ---------------------------------------------------------------------


@pytest.fixture
def at_fork(mini):
    """Waiting inside ``fork``, whose right branch moves ``Location`` where no situation matches."""
    return choose(mini, start(mini).state, "begin::fork").state


def test_no_matching_situation_halts_as_a_dead_end(mini, at_fork):
    dead_end = choose(mini, at_fork, "begin::fork::go-right")

    assert dead_end.state.status is Status.HALTED
    assert dead_end.state.outcome == Outcome("", dead_end=True)


def test_dead_end_clears_the_stack_and_offers_nothing(mini, at_fork):
    dead_end = choose(mini, at_fork, "begin::fork::go-right")

    assert dead_end.state.stack == ()
    assert dead_end.state.offered == ()
    assert not any(isinstance(output, ChoicesOffered) for output in dead_end.outputs)


def test_dead_end_emits_halted_last(mini, at_fork):
    dead_end = choose(mini, at_fork, "begin::fork::go-right")

    assert dead_end.outputs[-2:] == (SituationExited("begin::fork"), Halted("", dead_end=True))
    assert QualityChanged("Location", "Fork", "Nowhere") in dead_end.outputs


# --- Determinism ---------------------------------------------------------------------------


def test_start_is_deterministic(menu):
    first, second = start(menu), start(menu)

    assert first == second
    assert repr(first) == repr(second)


def test_choose_is_deterministic(mini):
    s0 = start(mini).state

    first, second = choose(mini, s0, "begin::fork"), choose(mini, s0, "begin::fork")

    assert first == second
    assert repr(first) == repr(second)


# --- Isolation (US2-AS7) -------------------------------------------------------------------


def test_two_interleaved_games_share_no_state(cloak):
    one, two = start(cloak), start(cloak)
    snapshot = repr(two)

    moved = choose(cloak, one.state, "begin::intro")

    assert one.state is not two.state
    assert moved.state != two.state
    assert repr(two) == snapshot
    assert two.state.status is Status.WAITING
    assert two.state.offered == ("begin::intro",)
    assert two.state.stack == ()


def test_choosing_leaves_the_input_state_unchanged(cloak):
    step = start(cloak)
    snapshot = repr(step.state)

    choose(cloak, step.state, "begin::intro")

    assert repr(step.state) == snapshot
