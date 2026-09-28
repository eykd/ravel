"""Unit tests for the engine's plain-data output types."""

import attrs
import pytest

from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Halted,
    QualityChanged,
    SituationEntered,
    SituationExited,
    Step,
    TextShown,
)
from ravel.engine.state import GameState, Qualities, Status

OPTION = ChoiceOption("begin::intro", "Hurrying through the rainswept November night…")

#: One instance of each output kind, built twice to prove value equality.
OUTPUT_FACTORIES = [
    lambda: TextShown("Hello."),
    lambda: OPTION,
    lambda: ChoicesOffered((OPTION,)),
    lambda: QualityChanged("Place", None, "Foyer"),
    lambda: SituationEntered("begin::intro"),
    lambda: SituationExited("begin::intro"),
    lambda: Halted("victory", False),
]
OUTPUT_IDS = [
    "TextShown",
    "ChoiceOption",
    "ChoicesOffered",
    "QualityChanged",
    "SituationEntered",
    "SituationExited",
    "Halted",
]


@pytest.mark.parametrize("factory", OUTPUT_FACTORIES, ids=OUTPUT_IDS)
def test_outputs_compare_and_hash_by_value(factory):
    assert factory() == factory()
    assert hash(factory()) == hash(factory())


@pytest.mark.parametrize("factory", OUTPUT_FACTORIES, ids=OUTPUT_IDS)
def test_outputs_are_frozen(factory):
    output = factory()
    first_field = attrs.fields(type(output))[0].name
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        setattr(output, first_field, "changed")


class TestTextShown:
    def test_sticky_defaults_to_false(self):
        assert TextShown("Hello.").sticky is False

    def test_sticky_text_differs_from_plain_text(self):
        assert TextShown("Hello.", sticky=True) != TextShown("Hello.")


class TestChoicesOffered:
    def test_it_holds_its_options_in_order(self):
        other = ChoiceOption("begin::fork", "At the fork")
        assert ChoicesOffered((OPTION, other)).choices == (OPTION, other)

    def test_it_rejects_an_empty_menu(self):
        with pytest.raises(ValueError):
            ChoicesOffered(())


class TestQualityChanged:
    def test_old_is_none_for_a_previously_unset_quality(self):
        change = QualityChanged(name="Place", old=None, new="Foyer")
        assert change.old is None

    def test_changes_with_different_old_values_are_unequal(self):
        assert QualityChanged("n", 1, 2) != QualityChanged("n", None, 2)


class TestSituationEvents:
    def test_entered_and_exited_are_distinct_events(self):
        assert SituationEntered("begin::intro") != SituationExited("begin::intro")


class TestHalted:
    def test_it_holds_the_outcome_and_dead_end_flag(self):
        halted = Halted(outcome="", dead_end=True)
        assert (halted.outcome, halted.dead_end) == ("", True)


class TestStep:
    def test_it_compares_by_value(self):
        state = GameState(
            qualities=Qualities(),
            stack=(),
            status=Status.HALTED,
            offered=(),
            outcome=None,
        )
        outputs = (TextShown("Bye."), Halted("", True))
        assert Step(state, outputs) == Step(state=state, outputs=outputs)
