"""Acceptance test for US2: a pure, re-entrant engine plays storylets correctly.

RED per ravel-8qa.5.2.1 -- expected to FAIL (``ravel.engine`` does not exist
yet) until the US2 Green leaves land. Drives only the public engine surface:
``ravel.engine.start``/``choose`` over a ``Story`` built from Cloak of Darkness
and the ``tests/fixtures/stories/mini`` fixture.
"""

from collections.abc import Iterator
from pathlib import Path

import attrs
import pytest

from ravel import engine
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Halted,
    QualityChanged,
    SituationEntered,
    SituationExited,
    TextShown,
)
from ravel.engine.state import Frame, Outcome, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

pytestmark = [pytest.mark.acceptance, pytest.mark.usefixtures("strict_conditions")]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"
MINI_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "mini"

INTRO_LABEL = "Hurrying through the rainswept November night…"
FOYER_MENU = ("foyer::outside", "foyer::foyer", "foyer::cloakroom", "foyer::bar")
MINI_START_MENU = ("begin::crossroads", "begin::fork", "begin::bridge")

#: The only attrs classes an output tree may contain: the output kinds themselves.
OUTPUT_CLASSES = frozenset(
    {TextShown, ChoiceOption, ChoicesOffered, QualityChanged, SituationEntered, SituationExited, Halted}
)
#: Exact plain-data leaf types (subclasses such as syml's str-likes are refused).
PLAIN_TYPES = frozenset({str, int, float, bool, type(None)})


def _load_story(path: Path) -> Story:
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=str(path))).load())


@pytest.fixture(scope="module")
def cloak() -> Story:
    return _load_story(CLOAK_PATH)


@pytest.fixture(scope="module")
def mini() -> Story:
    return _load_story(MINI_PATH)


def _offered_locations(outputs) -> tuple[str, ...]:
    menus = [output for output in outputs if isinstance(output, ChoicesOffered)]
    assert len(menus) == 1, f"expected exactly one menu, got {menus!r}"
    return tuple(option.location for option in menus[0].choices)


def _walk(value, path: str = "output") -> Iterator[tuple[str, object]]:
    """Yield every (path, value) node in an output tree."""
    yield path, value
    if type(value) is tuple:
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    elif attrs.has(type(value)):
        for field in attrs.fields(type(value)):
            yield from _walk(getattr(value, field.name), f"{path}.{field.name}")


def test_start_offers_only_the_intro_and_applies_givens_once(cloak, mini):
    """US2-AS1: a new Cloak game waits at the intro menu with its givens applied exactly once."""
    step = engine.start(cloak)

    assert step.state.status is Status.WAITING
    assert step.state.offered == ("begin::intro",)
    assert step.state.stack == ()
    assert step.outputs[:2] == (
        QualityChanged("Location", None, "Intro"),
        QualityChanged("Wearing Cloak", None, 1),
    )
    assert step.outputs[-1] == ChoicesOffered((ChoiceOption("begin::intro", INTRO_LABEL),))
    assert step.outputs.count(QualityChanged("Location", None, "Intro")) == 1
    assert step.outputs.count(QualityChanged("Wearing Cloak", None, 1)) == 1
    qualities = step.state.qualities.as_dict()
    assert qualities["Location"] == "Intro"
    assert qualities["Wearing Cloak"] == 1

    # A `+=` given is applied once, not twice (D1): Count goes 0 -> 1.
    mini_step = engine.start(mini)
    assert mini_step.outputs.count(QualityChanged("Count", None, 1)) == 1
    assert mini_step.state.qualities.get("Count") == 1


def test_choosing_intro_shows_tail_once_and_stops_at_its_choice_block(cloak):
    """US2-AS2: choosing begin::intro shows its tail text once and yields at the choice block."""
    s0 = engine.start(cloak)
    s1 = engine.choose(cloak, s0.state, "begin::intro")

    assert [type(output) for output in s1.outputs] == [SituationEntered, TextShown, ChoicesOffered]
    assert s1.outputs[0] == SituationEntered("begin::intro")
    tail = s1.outputs[1]
    assert tail.text.startswith("Hurrying through the rainswept November night, you're glad")
    assert "Opera House" in tail.text
    assert s1.outputs[2] == ChoicesOffered((ChoiceOption("begin::intro::press-onward", "Press onward!"),))

    assert s1.state.status is Status.WAITING
    assert s1.state.offered == ("begin::intro::press-onward",)
    assert s1.state.stack == (Frame("begin::intro", 4),)  # parked on GetChoice
    # Nothing after the choice block ran: no quality changed, Location still Intro.
    assert s1.state.qualities == s0.state.qualities
    assert s1.state.qualities.get("Location") == "Intro"


def test_gather_runs_only_after_the_chosen_sub_situation(mini):
    """US2-AS3: gather text and its effect run after the chosen sub-situation, in order."""
    s0 = engine.start(mini)
    s1 = engine.choose(mini, s0.state, "begin::fork")

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
    assert s1.state.stack == (Frame("begin::fork", 4),)
    assert s1.state.qualities.get("Place") is None  # gather not run yet
    assert all(not (isinstance(o, TextShown) and o.text == "The road rejoins.") for o in s1.outputs)

    s2 = engine.choose(mini, s1.state, "begin::fork::go-left")
    assert s2.outputs[:5] == (
        SituationEntered("begin::fork::go-left"),
        TextShown("You go left."),
        SituationExited("begin::fork::go-left"),
        TextShown("The road rejoins."),
        QualityChanged("Place", None, "Middle"),
    )
    assert s2.state.qualities.get("Place") == "Middle"


def test_finished_frames_pop_and_empty_stack_queries(cloak, mini):
    """US2-AS4: a situation past its last directive always pops; an empty stack then queries."""
    s0 = engine.start(cloak)
    s1 = engine.choose(cloak, s0.state, "begin::intro")
    s2 = engine.choose(cloak, s1.state, "begin::intro::press-onward")

    # press-onward finishes, then intro (nothing after its block) finishes: both pop, then query.
    assert s2.outputs[-3:-1] == (
        SituationExited("begin::intro::press-onward"),
        SituationExited("begin::intro"),
    )
    assert s2.state.stack == ()
    assert s2.state.status is Status.WAITING
    assert s2.state.offered == FOYER_MENU
    assert _offered_locations(s2.outputs) == FOYER_MENU

    # The same holds for the gather case: fork pops after its gather, then the query menu.
    m1 = engine.choose(mini, engine.start(mini).state, "begin::fork")
    m2 = engine.choose(mini, m1.state, "begin::fork::go-left")
    assert m2.outputs[5] == SituationExited("begin::fork")
    assert m2.state.stack == ()
    assert m2.state.offered == MINI_START_MENU


def test_query_menu_order_is_predicate_count_then_location_descending(cloak, mini):
    """US2-AS5: query menus sort by predicate count desc, then location ID desc, deterministically."""
    mini_step = engine.start(mini)
    assert mini_step.state.offered == MINI_START_MENU
    assert _offered_locations(mini_step.outputs) == MINI_START_MENU
    assert engine.start(mini) == mini_step  # same inputs, same step

    s1 = engine.choose(cloak, engine.start(cloak).state, "begin::intro")
    foyer_steps = [engine.choose(cloak, s1.state, "begin::intro::press-onward") for _ in range(3)]
    assert all(step.state.offered == FOYER_MENU for step in foyer_steps)
    assert foyer_steps[0] == foyer_steps[1] == foyer_steps[2]


def test_query_with_no_matches_halts_as_a_dead_end(mini):
    """US2-AS6: when no situation matches, the engine halts with a dead-end outcome and no menu."""
    s1 = engine.choose(mini, engine.start(mini).state, "begin::fork")
    s2 = engine.choose(mini, s1.state, "begin::fork::go-right")  # sets Location = "Nowhere"

    assert s2.state.status is Status.HALTED
    assert s2.state.outcome == Outcome("", dead_end=True)
    assert s2.state.offered == ()
    assert s2.state.stack == ()
    assert not any(isinstance(output, ChoicesOffered) for output in s2.outputs)
    assert s2.outputs[-1] == Halted("", True)


def test_interleaved_games_never_cross_contaminate(cloak):
    """US2-AS7: two games in one process, advanced alternately, match two solo runs exactly."""
    route = ("begin::intro", "begin::intro::press-onward", "foyer::cloakroom")

    def solo() -> list:
        step = engine.start(cloak)
        steps = [step]
        for location in route:
            step = engine.choose(cloak, step.state, location)
            steps.append(step)
        return steps

    expected = solo()

    a = [engine.start(cloak)]
    b = [engine.start(cloak)]
    for location in route:
        a.append(engine.choose(cloak, a[-1].state, location))
        # b lags one move behind a, so the two games sit at different points.
        assert b[-1] == expected[len(b) - 1]
        b.append(engine.choose(cloak, b[-1].state, location))

    assert a == expected
    assert b == expected
    # Re-choosing on an old state yields the same step again and leaves that state untouched.
    assert engine.choose(cloak, a[0].state, "begin::intro") == expected[1]
    assert a[0] == expected[0]


def test_outputs_hold_only_plain_immutable_data(cloak, mini):
    """US2-AS8: every output is plain data (str/int/float/bool/None/tuple) and never changes."""
    steps = [engine.start(cloak)]
    for location in ("begin::intro", "begin::intro::press-onward", "foyer::cloakroom"):
        steps.append(engine.choose(cloak, steps[-1].state, location))
    m1 = engine.choose(mini, engine.start(mini).state, "begin::fork")
    steps.append(m1)
    steps.append(engine.choose(mini, m1.state, "begin::fork::go-right"))

    snapshots = [repr(step.outputs) for step in steps]
    for step in steps:
        assert type(step.outputs) is tuple
        for path, value in _walk(step.outputs):
            kind = type(value)
            if kind is tuple:
                continue
            if attrs.has(kind):
                assert kind in OUTPUT_CLASSES, f"{path}: engine internal {kind.__qualname__} leaked"
                with pytest.raises(attrs.exceptions.FrozenInstanceError):
                    setattr(value, attrs.fields(kind)[0].name, None)
                continue
            assert kind in PLAIN_TYPES, f"{path}: {kind.__qualname__} is not plain data"
            assert not callable(value), f"{path}: callable leaked"

    # Later calls never change earlier outputs.
    engine.choose(cloak, steps[3].state, steps[3].state.offered[0])
    engine.start(mini)
    assert [repr(step.outputs) for step in steps] == snapshots
