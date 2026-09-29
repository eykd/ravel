"""Unit tests for ``start``: givens applied once each, then a run to the first menu."""

from pathlib import Path

import pytest

from ravel import types
from ravel.engine.engine import start
from ravel.engine.errors import InvalidOperationError, InvalidQualityValueError
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, QualityChanged
from ravel.engine.state import Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.exceptions import EvaluationError
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


def test_given_dividing_by_an_unset_quality_raises_invalid_operation():
    rulebook: types.CompiledRulebook = {
        "metadata": {},
        "rulebook": {"Situation": {"rules": [], "locations": {}}},
        "givens": [types.Operation("X", "=", types.Expression(10, "/", types.QualityRef("Zero")))],
    }

    with pytest.raises(InvalidOperationError) as excinfo:
        start(Story(rulebook=rulebook))

    assert isinstance(excinfo.value.__cause__, EvaluationError)
    assert isinstance(excinfo.value.__cause__.__cause__, ZeroDivisionError)


def test_given_with_a_max_constraint_is_clamped_in_the_emitted_change():
    rulebook: types.CompiledRulebook = {
        "metadata": {},
        "rulebook": {"Situation": {"rules": [], "locations": {}}},
        "givens": [types.Operation("Gold", "=", 50, types.Constraint("max", 20))],
    }

    step = start(Story(rulebook=rulebook))

    changes = [output for output in step.outputs if isinstance(output, QualityChanged)]
    assert changes == [QualityChanged("Gold", None, 20)]


def test_given_computing_an_oversize_int_raises_a_typed_error_with_a_short_message():
    big = 10**3999
    rulebook: types.CompiledRulebook = {
        "metadata": {},
        "rulebook": {"Situation": {"rules": [], "locations": {}}},
        "givens": [types.Operation("Y", "=", types.Expression(big, "*", big))],
    }

    with pytest.raises(InvalidQualityValueError) as excinfo:
        start(Story(rulebook=rulebook))

    assert len(str(excinfo.value)) < 200
