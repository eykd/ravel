"""Unit tests for ``start``: givens applied once each, then a run to the first menu."""

from pathlib import Path

import pytest

from ravel.engine.engine import start
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, QualityChanged
from ravel.engine.state import Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stories"


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


@pytest.fixture
def cloak(examples_path):
    return load_story(examples_path / "cloak")


@pytest.fixture
def mini():
    return load_story(FIXTURES / "mini")


def test_start_cloak_emits_begin_givens_first(cloak):
    step = start(cloak)

    assert step.outputs[:2] == (
        QualityChanged("Location", None, "Intro"),
        QualityChanged("Wearing Cloak", None, 1),
    )


def test_start_cloak_applies_every_given_exactly_once(cloak):
    step = start(cloak)

    changes = [output for output in step.outputs if isinstance(output, QualityChanged)]
    assert [change.name for change in changes] == [given.quality for given in cloak.givens]


def test_start_cloak_ends_on_the_intro_menu(cloak):
    step = start(cloak)

    assert step.outputs[-1] == ChoicesOffered(
        (ChoiceOption("begin::intro", "Hurrying through the rainswept November night…"),)
    )


def test_start_cloak_leaves_the_game_waiting_on_the_intro(cloak):
    state = start(cloak).state

    assert state.status is Status.WAITING
    assert state.offered == ("begin::intro",)
    assert state.stack == ()
    assert state.outcome is None
    qualities = state.qualities.as_dict()
    assert qualities["Location"] == "Intro"
    assert qualities["Wearing Cloak"] == 1


def test_start_mini_applies_givens_in_order_from_unset(mini):
    step = start(mini)

    assert step.outputs[:2] == (
        QualityChanged("Count", None, 1),
        QualityChanged("Location", None, "Fork"),
    )
    assert step.state.qualities.as_dict() == {"Count": 1, "Location": "Fork"}


def test_start_mini_offers_the_matching_situations(mini):
    step = start(mini)

    assert isinstance(step.outputs[-1], ChoicesOffered)
    assert set(step.state.offered) == {"begin::crossroads", "begin::fork", "begin::bridge"}
    assert step.state.status is Status.WAITING
