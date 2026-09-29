"""Unit tests for the engine's immutable state value types."""

import math

import attrs
import pytest

from ravel.engine.errors import EngineError, InvalidQualityValueError
from ravel.engine.state import (
    INT_QUALITY_RANGE,
    QUALITY_TYPES,
    Frame,
    GameState,
    Outcome,
    Qualities,
    Status,
)
from ravel.types import MAX_STRING_LENGTH

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1


class TestScalars:
    def test_quality_types_are_int_float_and_str(self):
        assert (int, float, str) == QUALITY_TYPES

    def test_int_quality_range_is_signed_64_bit(self):
        assert range(INT_MIN, INT_MAX + 1) == INT_QUALITY_RANGE


class TestInvalidQualityValueError:
    def test_it_is_an_engine_error(self):
        assert issubclass(InvalidQualityValueError, EngineError)


class TestQualitiesFromMapping:
    def test_it_sorts_items_by_name(self):
        qualities = Qualities.from_mapping({"b": 2, "a": "one", "c": 3.5})
        assert qualities.items == (("a", "one"), ("b", 2), ("c", 3.5))

    def test_an_empty_mapping_gives_empty_qualities(self):
        assert Qualities.from_mapping({}) == Qualities()

    def test_equal_mappings_give_equal_and_equally_hashed_values(self):
        first = Qualities.from_mapping({"a": 1, "b": 2})
        second = Qualities.from_mapping({"b": 2, "a": 1})
        assert first == second
        assert hash(first) == hash(second)

    def test_it_rejects_an_invalid_value(self):
        with pytest.raises(InvalidQualityValueError):
            Qualities.from_mapping({"a": True})


class TestQualitiesInvariant:
    def test_it_rejects_unsorted_items(self):
        with pytest.raises(ValueError):
            Qualities(items=(("b", 1), ("a", 2)))

    def test_it_rejects_duplicate_names(self):
        with pytest.raises(ValueError):
            Qualities(items=(("a", 1), ("a", 2)))


class TestQualitiesGet:
    def test_it_returns_a_set_value(self):
        assert Qualities.from_mapping({"a": 1}).get("a") == 1

    def test_it_returns_none_for_an_unset_name(self):
        assert Qualities.from_mapping({"a": 1}).get("b") is None


class TestQualitiesSet:
    def test_it_returns_new_qualities_with_the_value_set(self):
        original = Qualities.from_mapping({"b": 2})
        updated = original.set("a", 1)
        assert updated.items == (("a", 1), ("b", 2))

    def test_it_replaces_an_existing_value(self):
        updated = Qualities.from_mapping({"a": 1}).set("a", "two")
        assert updated.items == (("a", "two"),)

    def test_it_leaves_the_original_unchanged(self):
        original = Qualities.from_mapping({"a": 1})
        original.set("a", 2)
        assert original.get("a") == 1

    @pytest.mark.parametrize("value", [0, INT_MIN, INT_MAX, 1.5, -0.0, "", "text", "café"])
    def test_it_accepts_a_storable_value(self, value):
        assert Qualities().set("q", value).get("q") == value

    @pytest.mark.parametrize(
        "value",
        [
            True,
            False,
            math.nan,
            math.inf,
            -math.inf,
            INT_MAX + 1,
            INT_MIN - 1,
            "\udc80",
            "ok\ud800",
            None,
            [1],
        ],
        ids=[
            "true",
            "false",
            "nan",
            "inf",
            "-inf",
            "int-above-range",
            "int-below-range",
            "lone-low-surrogate",
            "lone-high-surrogate",
            "none",
            "list",
        ],
    )
    def test_it_rejects_an_unstorable_value(self, value):
        with pytest.raises(InvalidQualityValueError):
            Qualities().set("q", value)

    def test_it_stores_a_string_at_the_length_cap_and_rejects_one_over(self):
        assert Qualities().set("q", "a" * MAX_STRING_LENGTH).get("q") == "a" * MAX_STRING_LENGTH
        with pytest.raises(InvalidQualityValueError):
            Qualities().set("q", "a" * (MAX_STRING_LENGTH + 1))

    def test_it_rejects_a_name_with_a_lone_surrogate(self):
        with pytest.raises(InvalidQualityValueError):
            Qualities().set("bad\udc80", 1)


class TestQualitiesAsDict:
    def test_it_returns_the_qualities_as_a_dict(self):
        assert Qualities.from_mapping({"b": 2, "a": 1}).as_dict() == {"a": 1, "b": 2}

    def test_it_returns_a_fresh_dict_each_call(self):
        qualities = Qualities.from_mapping({"a": 1})
        first = qualities.as_dict()
        first["a"] = 99
        assert qualities.as_dict() == {"a": 1}
        assert qualities.as_dict() is not qualities.as_dict()


class TestFrame:
    def test_it_compares_by_value(self):
        assert Frame("begin::intro", 2) == Frame(location="begin::intro", ip=2)
        assert hash(Frame("begin::intro", 2)) == hash(Frame("begin::intro", 2))

    def test_frames_differing_in_ip_are_unequal(self):
        assert Frame("begin::intro", 1) != Frame("begin::intro", 2)

    def test_it_is_frozen(self):
        frame = Frame("begin::intro", 0)
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            frame.ip = 1  # type: ignore[misc]


class TestStatus:
    @pytest.mark.parametrize(
        "status, value",
        [(Status.RUNNING, "running"), (Status.WAITING, "waiting_input"), (Status.HALTED, "halted")],
    )
    def test_it_has_string_values(self, status, value):
        assert status == value
        assert Status(value) is status

    def test_it_has_exactly_three_members(self):
        assert list(Status) == [Status.RUNNING, Status.WAITING, Status.HALTED]


class TestOutcome:
    def test_dead_end_defaults_to_false(self):
        assert Outcome("victory").dead_end is False

    def test_it_compares_by_value(self):
        assert Outcome("", dead_end=True) == Outcome(label="", dead_end=True)
        assert Outcome("victory") != Outcome("victory", dead_end=True)


def make_waiting_state():
    return GameState(
        qualities=Qualities.from_mapping({"Place": "Foyer"}),
        stack=(Frame("begin::intro", 3),),
        status=Status.WAITING,
        offered=("begin::intro::press-onward",),
        outcome=None,
    )


class TestGameState:
    def test_equal_states_are_equal_and_equally_hashed(self):
        assert make_waiting_state() == make_waiting_state()
        assert hash(make_waiting_state()) == hash(make_waiting_state())

    def test_states_differing_in_qualities_are_unequal(self):
        other = attrs.evolve(make_waiting_state(), qualities=Qualities.from_mapping({"Place": "Bar"}))
        assert other != make_waiting_state()

    def test_a_halted_state_carries_its_outcome(self):
        state = GameState(
            qualities=Qualities(),
            stack=(),
            status=Status.HALTED,
            offered=(),
            outcome=Outcome("victory"),
        )
        assert state.outcome == Outcome("victory")

    def test_it_is_frozen(self):
        state = make_waiting_state()
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            state.status = Status.HALTED  # type: ignore[misc]


class TestUnstorableValueMessage:
    def test_it_describes_an_oversize_string_without_embedding_it(self):
        with pytest.raises(InvalidQualityValueError) as excinfo:
            Qualities().set("q", "a" * (MAX_STRING_LENGTH + 1))
        assert len(str(excinfo.value)) < 200

    @pytest.mark.parametrize("value", [True, float("nan"), None, [1]], ids=["bool", "float", "none", "list"])
    def test_it_keeps_the_message_short_for_other_types(self, value):
        with pytest.raises(InvalidQualityValueError) as excinfo:
            Qualities().set("q" * 1000, value)
        assert len(str(excinfo.value)) < 200
