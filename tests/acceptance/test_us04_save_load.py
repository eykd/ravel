"""Acceptance test for US4: save and load a game.

RED per ravel-8qa.5.4.1, rewritten per ravel-8qa.5.4.6 for the 2026-09-28 design revision
(anchored, rulebook-independent saves -- see specs/001-reentrant-vm/spec.md SS Clarifications SS
Session 2026-09-28, contracts/save-format.md, contracts/session-api.md, contracts/engine-api.md).
Still expected to FAIL with a collection-time ``ModuleNotFoundError`` on ``ravel.app``
(``ravel.app``, ``ravel.adapters.save_store``, ``ravel.adapters.story_source``, and
``ravel.engine.outputs.StoryChanged`` don't exist yet) until the US4 Green leaves land
(ravel-8qa.5.4.2 onward).
"""

import json
import shutil
from pathlib import Path

import pytest

from ravel.adapters.save_store import FileSaveStore
from ravel.adapters.story_source import FileSystemStorySource
from ravel.app import (
    GameSession,
    LoadRefusedError,
    SaveCorruptError,
    UnsupportedSaveVersionError,
)
from ravel.engine.errors import GameOverError
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, QualityChanged, StoryChanged
from ravel.engine.state import Outcome, Status

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"
MINI_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "mini"
DUPLICATE_BLOCKS_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "duplicate-blocks"


def _cloak_source() -> FileSystemStorySource:
    return FileSystemStorySource(CLOAK_PATH)


def _mini_source() -> FileSystemStorySource:
    return FileSystemStorySource(MINI_PATH)


def _duplicate_blocks_source() -> FileSystemStorySource:
    return FileSystemStorySource(DUPLICATE_BLOCKS_PATH)


def test_saving_at_a_menu_produces_a_canonical_save_with_the_documented_fields(tmp_path):
    """US4-AS1/FR-022: a save at a menu is canonical JSON with format and state fields."""
    story = _cloak_source().load()
    session = GameSession(story, FileSaveStore(tmp_path))
    session.new_game()
    session.choose("begin::intro")  # -> waiting at the Foyer query menu

    path = session.save("mid.json")
    assert path

    data = (tmp_path / "mid.json").read_bytes()
    assert data.startswith(b'{"format":"ravel-save"')
    assert data.endswith(b"\n")

    # Canonical: sorted keys, tight separators, no ASCII escaping, no NaN/Infinity, re-encoding
    # the parsed document byte-for-byte reproduces the file.
    doc = json.loads(data)
    recanonicalized = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert recanonicalized.encode("utf-8") + b"\n" == data

    assert set(doc) == {"format", "format_version", "state"}
    assert doc["format"] == "ravel-save"
    assert doc["format_version"] == 1

    state = doc["state"]
    assert set(state) == {"qualities", "stack", "status", "outcome"}
    assert state["status"] == "waiting_input"
    assert state["outcome"] is None

    qualities = state["qualities"]
    assert type(qualities["Wearing Cloak"]) is int
    assert qualities["Wearing Cloak"] == 1
    assert type(qualities["Location"]) is str
    assert qualities["Location"] == "Foyer"

    # A save no longer carries a raw `ip`: each stack frame is named by its `location` plus an
    # `anchor` -- the choice block's own targets (`choices`) and a disambiguating `ordinal` --
    # never the ip (data-model.md SS Choice blocks, anchors, and saved frames).
    assert len(state["stack"]) == 1
    assert all(set(entry) == {"location", "anchor"} for entry in state["stack"])
    assert all(set(entry["anchor"]) == {"choices", "ordinal"} for entry in state["stack"])

    top = state["stack"][-1]
    assert top["location"] == session.state.stack[-1].location == "begin::intro"
    # The anchor's choices match the offered menu; Cloak has no duplicated choice blocks here,
    # so the ordinal is 0.
    assert top["anchor"]["choices"] == list(session.state.offered)
    assert top["anchor"]["ordinal"] == 0


def test_loading_restores_state_without_reapplying_givens_and_represents_the_menu(tmp_path):
    """US4-AS2/FR-023: load restores equal state, never re-runs givens, and re-shows the menu."""
    # A `+=` given (D1, D13): loading must not run it a second time.
    mini = _mini_source().load()
    a = GameSession(mini, FileSaveStore(tmp_path))
    a.new_game()
    a.save("mini.json")
    assert a.state.qualities.get("Count") == 1

    b = GameSession(mini, FileSaveStore(tmp_path))
    outs = b.load("mini.json")

    assert b.state == a.state
    assert not any(isinstance(output, QualityChanged) for output in outs)
    # The pending menu is re-presented with the same labels/order as before the save.
    menu_outputs = [output for output in outs if isinstance(output, ChoicesOffered)]
    assert len(menu_outputs) == 1
    assert menu_outputs[0].choices == b.menu()
    assert b.menu()

    # The session-api contract example (US4-AS2/AS3), against Cloak.
    story = _cloak_source().load()
    c = GameSession(story, FileSaveStore(tmp_path))
    c.new_game()
    c.choose("begin::intro")
    c.save("cloak-mid.json")

    d = GameSession(story, FileSaveStore(tmp_path))
    d_outs = d.load("cloak-mid.json")

    assert d_outs == (ChoicesOffered((ChoiceOption("begin::intro::press-onward", "Press onward!"),)),)
    assert d.state == c.state
    assert d.choose("begin::intro::press-onward") == c.choose("begin::intro::press-onward")


def test_save_mid_game_then_load_and_continue_matches_an_uninterrupted_run(tmp_path):
    """US4-AS3/FR-025: save/load/continue matches continuing uninterrupted, byte-identical finals."""
    story = _cloak_source().load()
    remaining = (
        "foyer::cloakroom",
        "cloakroom::look",
        "cloakroom::look",
        "cloakroom::look",
        "cloakroom::hang-up-cloak",
        "cloakroom::leave",
        "foyer::bar",
        "bar-light::look",
        "bar-light::look",
        "bar-light::look-at-message",
    )

    uninterrupted = GameSession(story, FileSaveStore(tmp_path))
    uninterrupted.new_game()
    uninterrupted.choose("begin::intro")
    uninterrupted.choose("begin::intro::press-onward")
    expected_outputs = [uninterrupted.choose(location) for location in remaining]

    interrupted = GameSession(story, FileSaveStore(tmp_path))
    interrupted.new_game()
    interrupted.choose("begin::intro")
    interrupted.choose("begin::intro::press-onward")
    interrupted.save("split.json")

    resumed = GameSession(story, FileSaveStore(tmp_path))
    resumed.load("split.json")
    resumed_outputs = [resumed.choose(location) for location in remaining]

    assert resumed_outputs == expected_outputs
    assert resumed.state == uninterrupted.state
    assert resumed.state.status is Status.HALTED
    assert resumed.state.outcome == Outcome("won", dead_end=False)

    uninterrupted.save("final-uninterrupted.json")
    resumed.save("final-resumed.json")
    assert (tmp_path / "final-uninterrupted.json").read_bytes() == (tmp_path / "final-resumed.json").read_bytes()


def test_loading_against_a_changed_story_is_degraded_not_refused(tmp_path):
    """US4-AS4 (2026-09-28 revision)/FR-024: a changed story never refuses a load. ``resume``
    degrades it instead -- truncating the stale part of the stack and reporting it via a leading
    ``StoryChanged`` -- per save-format.md's round-trip laws (a)-(c). (d), the
    ordinal-disambiguation case, is its own test below."""
    mini = _mini_source().load()
    live = GameSession(mini, FileSaveStore(tmp_path))
    live.new_game()
    live.choose("begin::bridge")
    live.choose("begin::bridge::follow-the-tunnel")
    expected_menu = live.menu()
    assert expected_menu == (
        ChoiceOption("begin::bridge::follow-the-tunnel::press-onward-into-the-dark", "Press onward into the dark"),
        ChoiceOption("begin::bridge::follow-the-tunnel::turn-back-to-the-bridge", "Turn back to the bridge"),
    )
    live.save("mid.json")
    state_before = live.state

    # (a) a benign edit elsewhere in the story (an unrelated situation, "crossroads") -> load
    # succeeds, resumes at the very same menu, and emits no `StoryChanged` at all -- the anchor
    # still matches.
    benign_dir = tmp_path / "benign-edit"
    shutil.copytree(MINI_PATH, benign_dir)
    benign_ravel = benign_dir / "begin.ravel"
    benign_ravel.write_text(
        benign_ravel.read_text(encoding="utf-8").replace(
            "The signpost points every which way.",
            "The signpost points every which way, uselessly.",
        ),
        encoding="utf-8",
    )
    benign_story = FileSystemStorySource(benign_dir).load()
    benign_session = GameSession(benign_story, FileSaveStore(tmp_path))
    benign_outs = benign_session.load("mid.json")

    assert benign_outs == (ChoicesOffered(expected_menu),)
    assert not any(isinstance(output, StoryChanged) for output in benign_outs)
    assert benign_session.state == state_before
    assert live.state == state_before  # the live session's own state is never touched by a load

    # (a), sharper variant: a line added *inside* the saved choice block's own situation, above
    # the block itself, shifts every directive index after it -- proving the anchor (the choice
    # block's own content), not the old raw `ip`, is what's actually being matched. The anchor
    # tuple itself is untouched, so this still resumes clean, with no `StoryChanged`; only the
    # frame's underlying ip differs, so this asserts the menu/qualities/stack shape rather than
    # `state == state_before`.
    shifted_dir = tmp_path / "shifted-ip"
    shutil.copytree(MINI_PATH, shifted_dir)
    shifted_ravel = shifted_dir / "begin.ravel"
    shifted_ravel.write_text(
        shifted_ravel.read_text(encoding="utf-8").replace(
            "      - [Follow the tunnel]You follow a tunnel deeper underground.\n",
            "      - [Follow the tunnel]You follow a tunnel deeper underground.\n"
            "      - It is dark and close in here.\n",
        ),
        encoding="utf-8",
    )
    shifted_story = FileSystemStorySource(shifted_dir).load()
    shifted_session = GameSession(shifted_story, FileSaveStore(tmp_path))
    shifted_outs = shifted_session.load("mid.json")

    assert shifted_outs == (ChoicesOffered(expected_menu),)
    assert not any(isinstance(output, StoryChanged) for output in shifted_outs)
    assert shifted_session.menu() == expected_menu
    assert shifted_session.state.qualities == state_before.qualities
    assert [frame.location for frame in shifted_session.state.stack] == [frame.location for frame in state_before.stack]

    # (b) deleting the saved (bottom) situation entirely -> every frame above it is dropped too,
    # `StoryChanged` names them all bottom-to-top, and the state re-derives a fresh top-level
    # query menu from the saved qualities.
    deleted_dir = tmp_path / "deleted-bridge"
    shutil.copytree(MINI_PATH, deleted_dir)
    deleted_ravel = deleted_dir / "begin.ravel"
    original = deleted_ravel.read_text(encoding="utf-8")
    bridge_start = original.index("bridge:")
    bridge_end = original.index("dead-end:")
    deleted_ravel.write_text(original[:bridge_start] + original[bridge_end:], encoding="utf-8")
    deleted_story = FileSystemStorySource(deleted_dir).load()

    deleted_session = GameSession(deleted_story, FileSaveStore(tmp_path))
    deleted_outs = deleted_session.load("mid.json")

    assert deleted_outs[0] == StoryChanged(dropped=("begin::bridge", "begin::bridge::follow-the-tunnel"))
    assert isinstance(deleted_outs[1], ChoicesOffered)
    assert len(deleted_outs) == 2
    assert deleted_session.state.stack == ()
    assert deleted_session.state.qualities == state_before.qualities

    # (c) changing the top frame's own choice block's targets -> only that frame (and anything
    # above it) is dropped; the parent frame survives and becomes the new top, re-offering its
    # own (unchanged) menu.
    retargeted_dir = tmp_path / "retargeted-tunnel"
    shutil.copytree(MINI_PATH, retargeted_dir)
    retargeted_ravel = retargeted_dir / "begin.ravel"
    retargeted_ravel.write_text(
        retargeted_ravel.read_text(encoding="utf-8").replace(
            "[Press onward into the dark]Something glints ahead in the dark.",
            "[Press onward into the darkness]Something glints ahead in the dark.",
        ),
        encoding="utf-8",
    )
    retargeted_story = FileSystemStorySource(retargeted_dir).load()

    retargeted_session = GameSession(retargeted_story, FileSaveStore(tmp_path))
    retargeted_outs = retargeted_session.load("mid.json")

    assert retargeted_outs[0] == StoryChanged(dropped=("begin::bridge::follow-the-tunnel",))
    assert len(retargeted_session.state.stack) == 1
    assert retargeted_session.state.stack[-1].location == "begin::bridge"
    assert retargeted_outs[1] == ChoicesOffered(
        (
            ChoiceOption("begin::bridge::follow-the-tunnel", "Follow the tunnel"),
            ChoiceOption("begin::bridge::shout-into-the-void", "Shout into the void"),
        )
    )


@pytest.mark.parametrize(
    ("mutate", "expected_error", "message_fragment"),
    [
        pytest.param(lambda doc: None, SaveCorruptError, "not valid JSON", id="not-json"),
        pytest.param(
            lambda doc: doc["state"].__delitem__("stack"),
            SaveCorruptError,
            "stack",
            id="missing-field",
        ),
        pytest.param(
            lambda doc: doc.__setitem__("format_version", 2),
            UnsupportedSaveVersionError,
            "2",
            id="unsupported-version",
        ),
    ],
)
def test_each_corrupt_save_variant_is_refused_by_name_and_leaves_state_unchanged(
    tmp_path, mutate, expected_error, message_fragment
):
    """US4-AS5/FR-024: each corrupt-save variant names its problem and leaves state unchanged."""
    story = _cloak_source().load()
    store = FileSaveStore(tmp_path)
    good = GameSession(story, store)
    good.new_game()
    good.choose("begin::intro")
    good.save("good.json")

    save_path = tmp_path / "corrupt.json"
    if message_fragment == "not valid JSON":
        save_path.write_bytes(b"not json")
    else:
        doc = json.loads((tmp_path / "good.json").read_bytes())
        mutate(doc)
        save_path.write_text(json.dumps(doc), encoding="utf-8")

    session = GameSession(story, store)
    with pytest.raises(expected_error, match=message_fragment):
        session.load("corrupt.json")
    assert issubclass(expected_error, LoadRefusedError)

    with pytest.raises(Exception):  # noqa: B017, PT011 - NoGameError; this session never had a game
        _ = session.state


def test_loading_a_halted_save_restores_the_halt_and_rejects_further_choices(tmp_path):
    """US4-AS6/FR-024: loading a halted save keeps the halt/outcome and rejects any choice."""
    mini = _mini_source().load()
    played = GameSession(mini, FileSaveStore(tmp_path))
    played.new_game()
    played.choose("begin::bridge")
    played.choose("begin::bridge::follow-the-tunnel")
    played.choose("begin::bridge::follow-the-tunnel::press-onward-into-the-dark")

    assert played.state.status is Status.HALTED
    assert played.state.outcome == Outcome("won", dead_end=False)
    played.save("halted.json")

    loaded = GameSession(mini, FileSaveStore(tmp_path))
    loaded.load("halted.json")

    assert loaded.state.status is Status.HALTED
    assert loaded.state.outcome == Outcome("won", dead_end=False)
    assert loaded.menu() == ()

    with pytest.raises(GameOverError):
        loaded.choose("begin::bridge")


def test_saving_at_duplicate_choice_blocks_is_disambiguated_by_ordinal(tmp_path):
    """US4-AS4(d)/data-model.md SS Anchor: two choice blocks in one situation offering the exact
    same choice-target tuple are disambiguated by `ordinal`, not conflated -- a save taken at the
    first occurrence resumes at the first occurrence, and a save at the second resumes at the
    second, even though `anchor.choices` alone can't tell them apart."""
    duplicate = _duplicate_blocks_source().load()

    first = GameSession(duplicate, FileSaveStore(tmp_path))
    first.new_game()
    first.choose("begin::loop")
    assert first.menu() == (ChoiceOption("begin::loop::go-on", "Go on"),)
    first.save("ordinal-0.json")
    state_at_ordinal_0 = first.state
    outputs_after_ordinal_0 = first.choose("begin::loop::go-on")

    second = GameSession(duplicate, FileSaveStore(tmp_path))
    second.new_game()
    second.choose("begin::loop")
    second.choose("begin::loop::go-on")  # consumes the first (ordinal 0) block
    assert second.menu() == (ChoiceOption("begin::loop::go-on", "Go on"),)  # now at ordinal 1
    second.save("ordinal-1.json")
    state_at_ordinal_1 = second.state

    # The two saves are genuinely different states (the second has run the intervening effect),
    # so a resume that ignored `ordinal` and always resolved to the first match would conflate
    # them.
    assert state_at_ordinal_1 != state_at_ordinal_0
    assert state_at_ordinal_1.qualities.get("Visited") == 1
    assert state_at_ordinal_0.qualities.get("Visited") is None

    reloaded_0 = GameSession(duplicate, FileSaveStore(tmp_path))
    reloaded_0_outs = reloaded_0.load("ordinal-0.json")
    assert reloaded_0.state == state_at_ordinal_0
    assert not any(isinstance(output, StoryChanged) for output in reloaded_0_outs)
    assert reloaded_0.choose("begin::loop::go-on") == outputs_after_ordinal_0

    reloaded_1 = GameSession(duplicate, FileSaveStore(tmp_path))
    reloaded_1_outs = reloaded_1.load("ordinal-1.json")
    assert reloaded_1.state == state_at_ordinal_1
    assert not any(isinstance(output, StoryChanged) for output in reloaded_1_outs)
