"""Unit tests for ``ravel.app.saves``: canonical, rulebook-independent save encode/decode.

Per contracts/save-format.md (2026-09-28 revision): ``encode_save(story, state)`` needs a story to
compute each frame's ``Anchor``; ``decode_save(data)`` is story-free -- it only parses and
shape-checks bytes, never checking whether any saved ``location`` exists in a story.
"""

import json

import pytest

from ravel import types
from ravel.app.saves import (
    MAX_SAVE_BYTES,
    SAVE_FORMAT,
    SAVE_FORMAT_VERSION,
    SAVE_MAGIC,
    LoadRefusedError,
    SaveCorruptError,
    UnsupportedSaveVersionError,
    decode_save,
    encode_save,
)
from ravel.engine.engine import choose, start
from ravel.engine.errors import InvalidStateError
from ravel.engine.state import Anchor, Frame, GameState, Outcome, Qualities, SavedFrame, SavedGame, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader


def load_story(path):
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=path)).load())


@pytest.fixture
def cloak(examples_path):
    return load_story(examples_path / "cloak")


@pytest.fixture
def mini():
    from pathlib import Path

    fixtures = Path(__file__).resolve().parent.parent / "fixtures" / "stories" / "mini"
    return load_story(fixtures)


def _canonical(doc):
    return (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


class TestEncodeSave:
    def test_it_produces_canonical_bytes_starting_with_the_magic_and_ending_with_a_newline(self, cloak):
        state = start(cloak).state

        data = encode_save(cloak, state)

        assert data.startswith(SAVE_MAGIC)
        assert data.endswith(b"\n")
        doc = json.loads(data)
        assert _canonical(doc) == data

    def test_it_encodes_the_documented_top_level_fields(self, cloak):
        state = start(cloak).state

        doc = json.loads(encode_save(cloak, state))

        assert set(doc) == {"format", "format_version", "state"}
        assert doc["format"] == SAVE_FORMAT
        assert doc["format_version"] == SAVE_FORMAT_VERSION
        assert set(doc["state"]) == {"qualities", "stack", "status", "outcome"}
        assert doc["state"]["status"] == "waiting_input"
        assert doc["state"]["outcome"] is None
        assert doc["state"]["stack"] == []

    def test_it_encodes_the_top_frames_anchor_from_the_offered_menu(self, cloak):
        step = choose(cloak, start(cloak).state, "begin::intro")
        state = step.state

        doc = json.loads(encode_save(cloak, state))

        assert len(doc["state"]["stack"]) == 1
        frame_doc = doc["state"]["stack"][0]
        assert set(frame_doc) == {"location", "anchor"}
        assert frame_doc["location"] == "begin::intro"
        assert set(frame_doc["anchor"]) == {"choices", "ordinal"}
        assert frame_doc["anchor"]["choices"] == list(state.offered)
        assert frame_doc["anchor"]["ordinal"] == 0

    def test_it_encodes_anchors_for_every_frame_including_non_top_frames(self, mini):
        state = start(mini).state
        state = choose(mini, state, "begin::bridge").state
        state = choose(mini, state, "begin::bridge::follow-the-tunnel").state

        doc = json.loads(encode_save(mini, state))

        stack = doc["state"]["stack"]
        assert [frame["location"] for frame in stack] == ["begin::bridge", "begin::bridge::follow-the-tunnel"]
        assert stack[0]["anchor"]["choices"] == [
            "begin::bridge::follow-the-tunnel",
            "begin::bridge::shout-into-the-void",
        ]
        assert stack[1]["anchor"]["choices"] == [
            "begin::bridge::follow-the-tunnel::press-onward-into-the-dark",
            "begin::bridge::follow-the-tunnel::turn-back-to-the-bridge",
        ]
        assert stack[0]["anchor"]["ordinal"] == 0
        assert stack[1]["anchor"]["ordinal"] == 0

    def test_it_encodes_a_halted_state(self, mini):
        state = start(mini).state
        state = choose(mini, state, "begin::bridge").state
        state = choose(mini, state, "begin::bridge::follow-the-tunnel").state
        state = choose(mini, state, "begin::bridge::follow-the-tunnel::press-onward-into-the-dark").state
        assert state.status is Status.HALTED

        doc = json.loads(encode_save(mini, state))

        assert doc["state"]["status"] == "halted"
        assert doc["state"]["stack"] == []
        assert doc["state"]["outcome"] == {"label": "won", "dead_end": False}

    def test_it_disambiguates_duplicate_choice_blocks_by_ordinal(self):
        directives = [
            types.Text("Loop."),
            types.BeginChoices(),
            types.Choice("s::go-on"),
            types.GetChoice(),
            types.Text("Again."),
            types.BeginChoices(),
            types.Choice("s::go-on"),
            types.GetChoice(),
        ]
        rulebook: types.CompiledRulebook = {
            "metadata": {},
            "rulebook": {
                "Situation": {
                    "rules": [types.Rule("s", [])],
                    "locations": {
                        "s": types.Situation(intro=types.Text("S"), directives=directives),
                        "s::go-on": types.Situation(intro=types.Text("Go on"), directives=[types.Text("...")]),
                    },
                }
            },
            "givens": [],
        }
        story = Story.from_rulebook(rulebook)
        state = GameState(
            qualities=Qualities(),
            stack=(Frame("s", 7),),
            status=Status.WAITING,
            offered=("s::go-on",),
            outcome=None,
        )

        doc = json.loads(encode_save(story, state))

        anchor = doc["state"]["stack"][0]["anchor"]
        assert anchor["choices"] == ["s::go-on"]
        assert anchor["ordinal"] == 1

    def test_it_raises_invalid_state_error_for_a_running_state(self, cloak):
        state = GameState(qualities=Qualities(), stack=(), status=Status.RUNNING, offered=(), outcome=None)

        with pytest.raises(InvalidStateError):
            encode_save(cloak, state)

    def test_it_raises_invalid_state_error_when_a_frames_ip_matches_no_choice_block(self, cloak):
        state = GameState(
            qualities=Qualities(),
            stack=(Frame("begin::intro", 999),),
            status=Status.WAITING,
            offered=("begin::intro::press-onward",),
            outcome=None,
        )

        with pytest.raises(InvalidStateError, match="no choice block"):
            encode_save(cloak, state)


class TestRoundTrip:
    def test_it_round_trips_a_top_level_query_menu(self, cloak):
        state = start(cloak).state

        data = encode_save(cloak, state)
        saved = decode_save(data)

        assert saved.qualities == state.qualities
        assert saved.status is state.status
        assert saved.outcome is None
        assert saved.stack == ()

    def test_it_round_trips_a_state_waiting_in_a_situation(self, cloak):
        state = choose(cloak, start(cloak).state, "begin::intro").state

        saved = decode_save(encode_save(cloak, state))

        assert saved.qualities == state.qualities
        assert len(saved.stack) == 1
        assert saved.stack[0] == SavedFrame(location="begin::intro", anchor=Anchor(choices=state.offered, ordinal=0))

    def test_it_round_trips_a_halted_state(self, mini):
        state = start(mini).state
        state = choose(mini, state, "begin::bridge").state
        state = choose(mini, state, "begin::bridge::shout-into-the-void").state
        assert state.status is Status.HALTED

        saved = decode_save(encode_save(mini, state))

        assert saved.status is Status.HALTED
        assert saved.stack == ()
        assert saved.outcome == Outcome("lost", dead_end=False)

    def test_encoding_is_byte_identical_across_two_encodes_of_an_equal_state(self, cloak):
        state = choose(cloak, start(cloak).state, "begin::intro").state

        assert encode_save(cloak, state) == encode_save(cloak, state)

    def test_json_int_decodes_to_int_and_float_decodes_to_float(self, mini):
        state = start(mini).state  # Count is given as `+= 1`, stored as JSON int 1

        doc = json.loads(encode_save(mini, state))
        assert doc["state"]["qualities"]["Count"] == 1
        assert type(doc["state"]["qualities"]["Count"]) is int

        doc["state"]["qualities"]["Ratio"] = 1.0
        data = _canonical(doc)
        saved = decode_save(data)

        assert type(saved.qualities.get("Count")) is int
        assert type(saved.qualities.get("Ratio")) is float

    def test_a_valid_surrogate_pair_is_accepted(self, cloak):
        state = start(cloak).state
        doc = json.loads(encode_save(cloak, state))
        doc["state"]["qualities"]["Emoji"] = "\U0001f600"  # a real character, valid UTF-8

        saved = decode_save(_canonical(doc))

        assert saved.qualities.get("Emoji") == "\U0001f600"


class TestDecodeSaveErrors:
    def _good_doc(self):
        return {
            "format": SAVE_FORMAT,
            "format_version": SAVE_FORMAT_VERSION,
            "state": {
                "qualities": {"Location": "Foyer", "Wearing Cloak": 1},
                "stack": [
                    {"location": "begin::intro", "anchor": {"choices": ["begin::intro::press-onward"], "ordinal": 0}}
                ],
                "status": "waiting_input",
                "outcome": None,
            },
        }

    def test_step0_rejects_a_save_over_the_size_cap(self):
        data = b"x" * (MAX_SAVE_BYTES + 1)
        with pytest.raises(SaveCorruptError, match="too large"):
            decode_save(data)

    def test_step1_rejects_invalid_json(self):
        with pytest.raises(SaveCorruptError, match="not valid JSON"):
            decode_save(b"not json")

    def test_step1_rejects_a_bom(self):
        with pytest.raises(SaveCorruptError, match="not valid JSON"):
            decode_save("﻿{}".encode())

    def test_step1_rejects_duplicate_keys(self):
        data = b'{"format":"ravel-save","format_version":1,"format_version":2}'
        with pytest.raises(SaveCorruptError, match="duplicate key 'format_version'"):
            decode_save(data)

    def test_step1_rejects_nan_and_infinity(self):
        data = b'{"format":"ravel-save","format_version":1,"state":{"qualities":{"Bar":NaN}}}'
        with pytest.raises(SaveCorruptError, match="NaN/Infinity not allowed"):
            decode_save(data)

    def test_step1_rejects_runaway_recursion(self):
        with pytest.raises(SaveCorruptError, match="not valid JSON"):
            decode_save(b"[" * 100_000)

    def test_step2_rejects_a_non_ravel_format(self):
        doc = self._good_doc()
        doc["format"] = "something-else"
        with pytest.raises(SaveCorruptError, match="not a ravel save file"):
            decode_save(_canonical(doc))

    def test_step3_rejects_a_bool_format_version(self):
        doc = self._good_doc()
        doc["format_version"] = True
        with pytest.raises(SaveCorruptError):
            decode_save(_canonical(doc))

    def test_step3_rejects_an_unsupported_version(self):
        doc = self._good_doc()
        doc["format_version"] = 2
        with pytest.raises(UnsupportedSaveVersionError, match="2"):
            decode_save(_canonical(doc))
        assert issubclass(UnsupportedSaveVersionError, LoadRefusedError)

    def test_step4_rejects_unexpected_top_level_keys(self):
        doc = self._good_doc()
        doc["extra"] = 1
        with pytest.raises(SaveCorruptError, match="extra"):
            decode_save(_canonical(doc))

    def test_step4_rejects_a_missing_state_field(self):
        doc = self._good_doc()
        del doc["state"]["stack"]
        with pytest.raises(SaveCorruptError, match="stack"):
            decode_save(_canonical(doc))

    def test_step4_rejects_bool_refused_as_ordinal(self):
        doc = self._good_doc()
        doc["state"]["stack"][0]["anchor"]["ordinal"] = True
        with pytest.raises(SaveCorruptError, match="ordinal"):
            decode_save(_canonical(doc))

    def test_step4_rejects_an_empty_anchor_choices(self):
        doc = self._good_doc()
        doc["state"]["stack"][0]["anchor"]["choices"] = []
        with pytest.raises(SaveCorruptError, match="choices"):
            decode_save(_canonical(doc))

    def test_step4_rejects_a_lone_surrogate_in_a_quality_value(self):
        # A lone surrogate can't round-trip through `json.dumps`/`str.encode` (Python refuses to
        # encode it), so build the raw bytes directly, the way a hand-edited save file would.
        data = (
            b'{"format":"ravel-save","format_version":1,"state":{"outcome":null,'
            b'"qualities":{"Location":"\\udc80"},"stack":[],"status":"waiting_input"}}\n'
        )
        with pytest.raises(SaveCorruptError, match=r"state\.qualities\['Location'\]: string contains a lone surrogate"):
            decode_save(data)

    def test_step4_rejects_a_lone_surrogate_in_a_quality_name(self):
        data = (
            b'{"format":"ravel-save","format_version":1,"state":{"outcome":null,'
            b'"qualities":{"\\udc80":1},"stack":[],"status":"waiting_input"}}\n'
        )
        with pytest.raises(SaveCorruptError, match="not a valid quality name"):
            decode_save(data)

    def test_a_huge_duplicate_key_gives_a_bounded_message(self):
        key = "k" * 500_000
        data = ('{"format":"ravel-save","%s":1,"%s":2}' % (key, key)).encode()
        with pytest.raises(SaveCorruptError) as excinfo:
            decode_save(data)
        assert len(str(excinfo.value)) < 200

    def test_a_huge_quality_name_gives_a_bounded_message(self):
        doc = self._good_doc()
        doc["state"]["qualities"] = {"q" * 500_000: [1]}
        with pytest.raises(SaveCorruptError) as excinfo:
            decode_save(_canonical(doc))
        assert len(str(excinfo.value)) < 200

    def test_a_huge_stack_location_gives_a_bounded_message(self):
        doc = self._good_doc()
        doc["state"]["stack"].append({"location": "L" * 500_000, "anchor": {"choices": ["x"], "ordinal": 0}})
        with pytest.raises(SaveCorruptError) as excinfo:
            decode_save(_canonical(doc))
        assert len(str(excinfo.value)) < 200

    def test_a_huge_format_version_gives_a_bounded_message(self):
        doc = self._good_doc()
        doc["format_version"] = 10**4000
        with pytest.raises(UnsupportedSaveVersionError) as excinfo:
            decode_save(_canonical(doc))
        assert len(str(excinfo.value)) < 200

    def test_control_characters_in_a_saved_quality_name_are_escaped(self):
        doc = self._good_doc()
        doc["state"]["qualities"] = {"a\x1b[31mb": [1]}
        with pytest.raises(SaveCorruptError) as excinfo:
            decode_save(_canonical(doc))
        assert "\x1b" not in str(excinfo.value)

    def test_step4_rejects_an_invalid_status(self):
        doc = self._good_doc()
        doc["state"]["status"] = "running"
        with pytest.raises(SaveCorruptError, match="status"):
            decode_save(_canonical(doc))

    def test_step4_rejects_a_bool_quality_value(self):
        doc = self._good_doc()
        doc["state"]["qualities"]["Flag"] = True
        with pytest.raises(SaveCorruptError, match="qualities"):
            decode_save(_canonical(doc))

    @pytest.mark.parametrize("bad_value", [True, None, [1], {"a": 1}])
    def test_step4_rejects_arrays_objects_bool_and_null_as_quality_values(self, bad_value):
        doc = self._good_doc()
        doc["state"]["qualities"]["Bad"] = bad_value
        with pytest.raises(SaveCorruptError):
            decode_save(_canonical(doc))

    def test_step4_rejects_an_outcome_when_not_halted(self):
        doc = self._good_doc()
        doc["state"]["outcome"] = {"label": "won", "dead_end": False}
        with pytest.raises(SaveCorruptError, match="outcome"):
            decode_save(_canonical(doc))

    def test_step4_rejects_a_missing_outcome_when_halted(self):
        doc = self._good_doc()
        doc["state"]["status"] = "halted"
        doc["state"]["stack"] = []
        doc["state"]["outcome"] = None
        with pytest.raises(SaveCorruptError, match="outcome"):
            decode_save(_canonical(doc))

    def test_step4_rejects_halted_with_a_nonempty_stack(self):
        doc = self._good_doc()
        doc["state"]["status"] = "halted"
        doc["state"]["outcome"] = {"label": "won", "dead_end": False}
        with pytest.raises(SaveCorruptError, match="must be empty"):
            decode_save(_canonical(doc))

    def test_step5_rejects_an_inconsistent_stack(self):
        doc = self._good_doc()
        doc["state"]["stack"].append({"location": "nowhere", "anchor": {"choices": ["x"], "ordinal": 0}})
        with pytest.raises(
            SaveCorruptError, match=r"stack\[1\]: 'nowhere' is not one of the parent frame's offered choices"
        ):
            decode_save(_canonical(doc))

    def test_step5_accepts_a_consistent_three_frame_stack(self):
        doc = self._good_doc()
        doc["state"]["stack"] = [
            {"location": "a", "anchor": {"choices": ["b"], "ordinal": 0}},
            {"location": "b", "anchor": {"choices": ["c"], "ordinal": 0}},
            {"location": "c", "anchor": {"choices": ["c::x"], "ordinal": 0}},
        ]
        saved = decode_save(_canonical(doc))
        assert [frame.location for frame in saved.stack] == ["a", "b", "c"]

    def test_top_level_json_that_is_not_an_object_is_refused(self):
        with pytest.raises(SaveCorruptError, match="top-level value must be an object"):
            decode_save(b"[]\n")

    def test_a_non_object_state_is_refused(self):
        doc = self._good_doc()
        doc["state"] = "nope"
        with pytest.raises(SaveCorruptError, match="state: must be an object"):
            decode_save(_canonical(doc))

    def test_a_non_object_qualities_is_refused(self):
        doc = self._good_doc()
        doc["state"]["qualities"] = []
        with pytest.raises(SaveCorruptError, match="qualities"):
            decode_save(_canonical(doc))

    def test_a_too_large_int_quality_value_is_refused(self):
        doc = self._good_doc()
        doc["state"]["qualities"]["Big"] = 2**63
        with pytest.raises(SaveCorruptError, match="signed 64-bit range"):
            decode_save(_canonical(doc))

    def test_an_overflowing_float_quality_value_is_refused(self):
        # `1e400` is valid JSON number syntax, but overflows `float()` to `inf` -- not the same
        # code path as the literal `Infinity`/`NaN` tokens, which are already rejected upstream.
        data = self._doc_bytes_with_raw_state_field('"qualities":{"Ratio":1e400}')
        with pytest.raises(SaveCorruptError, match="must be finite"):
            decode_save(data)

    def test_a_non_object_anchor_is_refused(self):
        doc = self._good_doc()
        doc["state"]["stack"][0]["anchor"] = "nope"
        with pytest.raises(SaveCorruptError, match="anchor: must be an object"):
            decode_save(_canonical(doc))

    def test_a_non_object_stack_frame_is_refused(self):
        doc = self._good_doc()
        doc["state"]["stack"] = ["nope"]
        with pytest.raises(SaveCorruptError, match="stack\\[0\\]: must be an object"):
            decode_save(_canonical(doc))

    def test_a_non_string_location_is_refused(self):
        doc = self._good_doc()
        doc["state"]["stack"][0]["location"] = 1
        with pytest.raises(SaveCorruptError, match="location: must be a string"):
            decode_save(_canonical(doc))

    def test_a_non_array_stack_is_refused(self):
        doc = self._good_doc()
        doc["state"]["stack"] = "nope"
        with pytest.raises(SaveCorruptError, match="state.stack: must be an array"):
            decode_save(_canonical(doc))

    def test_a_non_object_outcome_is_refused(self):
        doc = self._good_doc()
        doc["state"]["status"] = "halted"
        doc["state"]["stack"] = []
        doc["state"]["outcome"] = "nope"
        with pytest.raises(SaveCorruptError, match="outcome: must be an object or null"):
            decode_save(_canonical(doc))

    def test_a_non_string_outcome_label_is_refused(self):
        doc = self._good_doc()
        doc["state"]["status"] = "halted"
        doc["state"]["stack"] = []
        doc["state"]["outcome"] = {"label": 1, "dead_end": False}
        with pytest.raises(SaveCorruptError, match="outcome.label: must be a string"):
            decode_save(_canonical(doc))

    def test_a_non_bool_outcome_dead_end_is_refused(self):
        doc = self._good_doc()
        doc["state"]["status"] = "halted"
        doc["state"]["stack"] = []
        doc["state"]["outcome"] = {"label": "won", "dead_end": 1}
        with pytest.raises(SaveCorruptError, match="outcome.dead_end: must be a bool"):
            decode_save(_canonical(doc))

    def _doc_bytes_with_raw_state_field(self, raw_state_json: str) -> bytes:
        """Build save bytes with a hand-written ``state`` object so a raw JSON token (e.g.
        ``1e400``, which `json.dumps` can never re-emit) reaches the decoder verbatim."""
        return (
            '{"format":"ravel-save","format_version":1,"state":{%s,'
            '"stack":[],"status":"waiting_input","outcome":null}}\n' % raw_state_json
        ).encode("utf-8")

    def test_an_unexpected_exception_is_wrapped_in_save_corrupt_error(self):
        with pytest.raises(SaveCorruptError, match="unexpected error decoding save"):
            decode_save("not bytes")  # type: ignore[arg-type]

    def test_a_location_absent_from_any_story_is_not_a_decode_error(self):
        """``decode_save`` has no story to check against -- see save-format.md's last section."""
        doc = self._good_doc()
        doc["state"]["stack"][0]["location"] = "nowhere::not-a-place"
        doc["state"]["stack"][0]["anchor"]["choices"] = ["nowhere::not-a-place"]

        saved = decode_save(_canonical(doc))

        assert saved.stack[0].location == "nowhere::not-a-place"

    def test_every_refusal_is_a_load_refused_error(self):
        for bad, expected in [
            (b"not json", SaveCorruptError),
        ]:
            with pytest.raises(expected):
                decode_save(bad)
            try:
                decode_save(bad)
            except LoadRefusedError:
                pass
            else:  # pragma: no cover - defensive; the above always raises
                pytest.fail("expected a LoadRefusedError")


def test_decode_save_never_calls_choice_blocks_or_touches_a_story(monkeypatch):
    """``decode_save`` is pure and story-free (contracts/save-format.md)."""
    import ravel.app.saves as saves_module

    def _boom(*args, **kwargs):  # pragma: no cover - only invoked if the contract is violated
        raise AssertionError("decode_save must never call choice_blocks")

    monkeypatch.setattr(saves_module, "choice_blocks", _boom)

    good = {
        "format": SAVE_FORMAT,
        "format_version": SAVE_FORMAT_VERSION,
        "state": {"qualities": {}, "stack": [], "status": "halted", "outcome": {"label": "", "dead_end": True}},
    }
    saved = decode_save(_canonical(good))
    assert isinstance(saved, SavedGame)
