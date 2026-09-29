"""Unit tests for ``ravel.app.session.GameSession`` (contracts/session-api.md, 2026-09-28 revision).

Uses an in-memory fake ``SaveStore`` throughout (a real file store is US4.L4's job -- see
``ravel-8qa.5.4.4``) and a real ``FileSystemStorySource`` against ``examples/cloak`` (plus edited
copies, for the truncation tests).
"""

import shutil
from pathlib import Path

import pytest
from attrs import evolve

from ravel import types
from ravel.adapters.story_source import FileSystemStorySource
from ravel.app.saves import (
    NoGameError,
    SaveCorruptError,
    SaveNotFoundError,
    SaveTooLargeError,
    SaveUnreadableError,
    encode_save,
)
from ravel.app.session import DEFAULT_SAVE_NAME, GameSession
from ravel.engine.errors import InvalidOperationError, NotOfferedError
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, Halted, StoryChanged
from ravel.engine.state import Status
from ravel.engine.story import Story

pytestmark = pytest.mark.usefixtures("strict_conditions")


class FakeSaveStore:
    """An in-memory ``SaveStore``: no filesystem, no real errors unless asked for."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def write(self, name: str, data: bytes) -> str:
        self.files[name] = data
        return "<memory>/%s" % name

    def read(self, name: str) -> bytes:
        try:
            return self.files[name]
        except KeyError:
            raise FileNotFoundError(name) from None


class RaisingSaveStore:
    """A ``SaveStore`` whose ``read`` always raises a given error, to prove the live state survives."""

    def __init__(self, error: OSError) -> None:
        self._error = error

    def write(self, name: str, data: bytes) -> str:
        raise AssertionError("write should not be called in this test")

    def read(self, name: str) -> bytes:
        raise self._error


@pytest.fixture
def cloak(examples_path):
    return FileSystemStorySource(examples_path / "cloak").load()


@pytest.fixture
def mini():
    fixtures = Path(__file__).resolve().parent.parent / "fixtures" / "stories" / "mini"
    return FileSystemStorySource(fixtures).load()


class TestStory:
    def test_it_exposes_the_compiled_story_the_session_plays(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        assert session.story is cloak


class TestBeforeAnyGame:
    def test_state_raises_no_game_error(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        with pytest.raises(NoGameError):
            _ = session.state

    def test_menu_returns_an_empty_tuple(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        assert session.menu() == ()

    def test_save_raises_no_game_error(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        with pytest.raises(NoGameError):
            session.save()


class TestNewGame:
    def test_it_returns_engine_starts_outputs_and_sets_state(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        outputs = session.new_game()

        assert any(isinstance(output, ChoicesOffered) for output in outputs)
        assert session.state.status is Status.WAITING
        assert session.state.qualities.get("Location") == "Intro"

    def test_it_replaces_any_current_state(self, cloak):
        session = GameSession(cloak, FakeSaveStore())
        session.new_game()
        session.choose("begin::intro")
        session.choose("begin::intro::press-onward")
        assert session.state.qualities.get("Location") == "Foyer"

        session.new_game()

        assert session.state.qualities.get("Location") == "Intro"


class TestChoose:
    def test_it_returns_engine_chooses_outputs_and_updates_state(self, cloak):
        session = GameSession(cloak, FakeSaveStore())
        session.new_game()

        outputs = session.choose("begin::intro")

        assert outputs
        assert session.state.qualities.get("Location") == "Intro"

    def test_an_engine_error_propagates_and_leaves_state_untouched(self, cloak):
        session = GameSession(cloak, FakeSaveStore())
        session.new_game()
        state_before = session.state

        with pytest.raises(NotOfferedError):
            session.choose("not::a::real::choice")

        assert session.state == state_before

    def test_it_raises_no_game_error_before_any_game_starts(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        with pytest.raises(NoGameError):
            session.choose("begin::intro")


class TestSave:
    def test_it_writes_encode_save_bytes_and_returns_a_display_path(self, cloak):
        store = FakeSaveStore()
        session = GameSession(cloak, store)
        session.new_game()
        session.choose("begin::intro")

        path = session.save("mid.json")

        assert path == "<memory>/mid.json"
        assert store.files["mid.json"] == encode_save(cloak, session.state)

    def test_an_oversize_save_propagates_save_too_large_and_never_touches_the_store(self, cloak):
        store = FakeSaveStore()
        session = GameSession(cloak, store)
        session.new_game()
        qualities = session.state.qualities
        for index in range(17):
            qualities = qualities.set("q%d" % index, "x" * 64_000)
        state = session.state
        session._state = evolve(state, qualities=qualities)

        with pytest.raises(SaveTooLargeError):
            session.save("big.json")

        assert store.files == {}

    def test_it_defaults_to_the_default_save_name(self, cloak):
        store = FakeSaveStore()
        session = GameSession(cloak, store)
        session.new_game()

        session.save()

        assert DEFAULT_SAVE_NAME in store.files


class TestLoad:
    def test_it_maps_file_not_found_to_save_not_found_error(self, cloak):
        session = GameSession(cloak, FakeSaveStore())

        with pytest.raises(SaveNotFoundError, match="'missing.json'"):
            session.load("missing.json")

    def test_it_maps_other_os_errors_to_save_unreadable_error_and_keeps_live_state(self, cloak):
        live = GameSession(cloak, FakeSaveStore())
        live.new_game()
        live.choose("begin::intro")
        state_before = live.state

        # A separate session sharing the same raising store proves *this* session's own state
        # (never assigned) stays unset, and the live session's state is untouched regardless.
        broken = GameSession(cloak, RaisingSaveStore(PermissionError(13, "Permission denied")))

        with pytest.raises(SaveUnreadableError, match="'save.json'"):
            broken.load("save.json")

        with pytest.raises(NoGameError):
            _ = broken.state
        assert live.state == state_before

    def test_a_corrupt_save_propagates_decode_saves_error_and_leaves_state_unset(self, cloak):
        store = FakeSaveStore()
        store.files["bad.json"] = b"not json"
        session = GameSession(cloak, store)

        with pytest.raises(SaveCorruptError):
            session.load("bad.json")

        with pytest.raises(NoGameError):
            _ = session.state

    def test_load_never_calls_present_separately_it_returns_resumes_outputs_verbatim(self, cloak):
        a = GameSession(cloak, FakeSaveStore())
        a.new_game()
        a.choose("begin::intro")
        store = a._saves  # the FakeSaveStore; reused so `b` can read what `a` wrote
        a.save("mid.json")

        b = GameSession(cloak, store)
        outs = b.load("mid.json")

        assert outs == (ChoicesOffered((ChoiceOption("begin::intro::press-onward", "Press onward!"),)),)
        assert not any(isinstance(output, StoryChanged) for output in outs)

    def test_it_restores_a_halted_save_and_menu_is_empty(self, mini):
        store = FakeSaveStore()
        played = GameSession(mini, store)
        played.new_game()
        played.choose("begin::bridge")
        played.choose("begin::bridge::follow-the-tunnel")
        played.choose("begin::bridge::follow-the-tunnel::press-onward-into-the-dark")
        assert played.state.status is Status.HALTED
        played.save("halted.json")

        loaded = GameSession(mini, store)
        outs = loaded.load("halted.json")

        assert outs == (Halted("won", False),)
        assert loaded.state.status is Status.HALTED
        assert loaded.menu() == ()

    def test_round_trip_reproduces_state_including_offered_and_every_frame(self, cloak):
        """FR-025: for an unchanged story, load reproduces the exact original state and menu."""
        a = GameSession(cloak, FakeSaveStore())
        a.new_game()
        a.choose("begin::intro")
        store = a._saves
        a.save("mid.json")
        state_before = a.state

        b = GameSession(cloak, store)
        b.load("mid.json")

        assert b.state == state_before
        assert b.state.offered == state_before.offered
        assert [frame.ip for frame in b.state.stack] == [frame.ip for frame in state_before.stack]
        assert b.menu() == (ChoiceOption("begin::intro::press-onward", "Press onward!"),)
        # The live session that produced the save is untouched by the second session's load.
        assert a.state == state_before

    def test_load_against_a_story_with_the_saved_situation_removed_truncates_and_reports_it(
        self, examples_path, tmp_path
    ):
        """A load never raises for a changed story -- it degrades via truncation instead."""
        story = FileSystemStorySource(examples_path / "cloak").load()
        store = FakeSaveStore()
        session = GameSession(story, store)
        session.new_game()
        session.choose("begin::intro")  # -> waiting at "begin::intro"'s own choice block
        session.save("mid.json")

        edited_dir = tmp_path / "cloak-edited"
        shutil.copytree(examples_path / "cloak", edited_dir)
        begin_file = edited_dir / "begin.ravel"
        begin_file.write_text(
            begin_file.read_text(encoding="utf-8").replace("intro:", "intro-renamed:"),
            encoding="utf-8",
        )
        edited_story = FileSystemStorySource(edited_dir).load()

        loaded = GameSession(edited_story, store)
        outs = loaded.load("mid.json")

        assert outs[0] == StoryChanged(dropped=("begin::intro",))
        assert isinstance(outs[1], ChoicesOffered)
        assert len(outs) == 2
        assert loaded.state.stack == ()
        # A successful (degraded) load still assigns state -- this is not a refusal.
        assert loaded.state.qualities.get("Location") == "Intro"


class TestChooseInvalidOperation:
    def test_an_invalid_operation_leaves_the_session_state_unchanged(self):
        rulebook: types.CompiledRulebook = {
            "metadata": {},
            "rulebook": {
                "Situation": {
                    "rules": [types.Rule("s", [])],
                    "locations": {
                        "s": types.Situation(
                            intro=types.Text("S"),
                            directives=[types.Operation("X", "=", types.Expression(10, "/", types.QualityRef("Zero")))],
                        )
                    },
                }
            },
            "givens": [],
        }
        session = GameSession(Story(rulebook=rulebook), FakeSaveStore())
        session.new_game()
        state_before = session.state

        with pytest.raises(InvalidOperationError):
            session.choose("s")

        assert session.state == state_before
