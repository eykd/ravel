"""Acceptance test for US4: save and load a game.

RED per ravel-8qa.5.4.1 -- expected to FAIL with a collection-time
``ModuleNotFoundError`` on ``ravel.app`` (``ravel.app``, ``ravel.adapters.save_store``, and
``ravel.adapters.story_source`` don't exist yet) until the US4 Green leaves land
(ravel-8qa.5.4.2 onward, per specs/001-reentrant-vm/contracts/session-api.md and
save-format.md).
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
    StoryChangedError,
    UnknownLocationError,
    UnsupportedSaveVersionError,
)
from ravel.engine.errors import GameOverError
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, QualityChanged
from ravel.engine.state import Outcome, Status

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"
MINI_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "mini"


def _cloak_source() -> FileSystemStorySource:
    return FileSystemStorySource(CLOAK_PATH)


def _mini_source() -> FileSystemStorySource:
    return FileSystemStorySource(MINI_PATH)


def test_saving_at_a_menu_produces_a_canonical_save_with_the_documented_fields(tmp_path):
    """US4-AS1/FR-022: a save at a menu is canonical JSON with format, identity, and state fields."""
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

    assert set(doc) == {"format", "format_version", "story_id", "state"}
    assert doc["format"] == "ravel-save"
    assert doc["format_version"] == 1
    assert doc["story_id"] == story.identity

    state = doc["state"]
    assert set(state) == {"qualities", "stack", "status", "offered", "outcome"}
    assert state["status"] == "waiting_input"
    assert state["outcome"] is None
    assert state["offered"] == list(session.state.offered)
    assert state["offered"]  # Foyer's menu is non-empty

    qualities = state["qualities"]
    assert type(qualities["Wearing Cloak"]) is int
    assert qualities["Wearing Cloak"] == 1
    assert type(qualities["Location"]) is str
    assert qualities["Location"] == "Foyer"

    assert state["stack"] == [{"location": frame.location, "ip": frame.ip} for frame in session.state.stack]
    assert all(set(entry) == {"location", "ip"} for entry in state["stack"])


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


def test_loading_against_a_changed_story_is_refused_and_leaves_state_untouched(tmp_path):
    """US4-AS4/FR-024: an edited (differently-compiled) story refuses the load and leaves state."""
    live_story = _cloak_source().load()
    live = GameSession(live_story, FileSaveStore(tmp_path))
    live.new_game()
    live.choose("begin::intro")
    live.save("mid.json")
    state_before = live.state

    edited_dir = tmp_path / "edited-cloak"
    shutil.copytree(CLOAK_PATH, edited_dir)
    begin_ravel = edited_dir / "begin.ravel"
    assert begin_ravel.exists()
    begin_ravel.write_text(
        begin_ravel.read_text(encoding="utf-8").replace("Press onward!", "Press onward now!"),
        encoding="utf-8",
    )
    edited_story = FileSystemStorySource(edited_dir).load()
    assert edited_story.identity != live_story.identity

    edited_session = GameSession(edited_story, FileSaveStore(tmp_path))
    with pytest.raises(StoryChangedError, match="story has changed"):
        edited_session.load("mid.json")

    # Nothing was assigned: the edited session still has no game, and the live session, whose
    # save this was, is completely untouched.
    with pytest.raises(Exception):  # noqa: B017, PT011 - NoGameError; asserting "no game" not its type
        _ = edited_session.state
    assert live.state == state_before

    # A positive control: identity derives from compiled content, not from the directory path, so
    # an unedited copy of the same story loads the same save without complaint.
    unedited_dir = tmp_path / "unedited-cloak"
    shutil.copytree(CLOAK_PATH, unedited_dir)
    unedited_story = FileSystemStorySource(unedited_dir).load()
    assert unedited_story.identity == live_story.identity
    unedited_session = GameSession(unedited_story, FileSaveStore(tmp_path))
    unedited_session.load("mid.json")
    assert unedited_session.state == live.state


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
        pytest.param(
            lambda doc: doc["state"].__setitem__("offered", ["nowhere::not-a-place"]),
            UnknownLocationError,
            "nowhere::not-a-place",
            id="unknown-location",
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
