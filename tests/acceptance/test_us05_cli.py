"""Acceptance test for US5: play, save, and load from the command line.

RED per ravel-8qa.5.5.1. Written per specs/001-reentrant-vm/spec.md SS US-5 AS1-AS8 and
specs/001-reentrant-vm/contracts/cli.md. Expected to FAIL against the current ``ravel.cli``: the
old runner-based CLI does not build on ``ravel.app.GameSession``,
takes no ``--load`` option, and does not match the prompt/error/rendering contract exercised
below (ravel-8qa.5.5.2 rewrites ``cli.py`` as a thin ``ConsoleUI`` adapter to make this pass).

Uses ``tests/fixtures/stories/mini`` (see ``tests/acceptance/test_us02_engine.py`` and
``test_us04_save_load.py`` for the same fixture's shape) rather than ``examples/cloak`` for
brevity -- it is a handful of situations deep with a clean "won" path and a clean dead end.
"""

import builtins
import pdb
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

import ravel.cli as cli

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MINI_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "mini"
DEFAULT_SAVE_NAME = "ravel-save.json"

PROMPT = "What'll it be?"


def _run(args, input_text=None, **kwargs):
    runner = CliRunner()
    return runner.invoke(cli.main, args, input=input_text, **kwargs)


# --- (1) the intro menu shows once, the opening choice is never asked twice ---------------------


def test_intro_menu_shown_once_and_prompt_never_repeats_the_menu(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "q\n")

    assert result.exit_code == 0
    assert result.output.count(PROMPT) == 1
    assert "1: Study the signpost" in result.output
    assert "2: You stand at a fork." in result.output
    assert "3: Cross the bridge" in result.output


# --- (2) a valid menu number chooses; other non-command input is rejected with a re-prompt ------


def test_valid_choice_advances_and_invalid_input_is_rejected_with_reprompt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "99\nbanana\n2\nq\n")

    assert result.exit_code == 0
    assert result.output.count("That's not an option.") == 1
    assert result.output.count("I'm sorry, what?") == 1
    # choosing 2 (the fork) advances to the fork's own menu
    assert "1: Go left" in result.output
    assert "2: Go right" in result.output


# --- (3) save/save FILE writes a snapshot, prints its path, same menu still waits ---------------


def test_save_default_and_named_write_snapshots_print_their_path_and_overwrite(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "save\nsave mine.json\nsave mine.json\nq\n")

    default_path = tmp_path / DEFAULT_SAVE_NAME
    named_path = tmp_path / "mine.json"

    assert result.exit_code == 0
    assert default_path.exists()
    assert named_path.exists()
    assert f"Saved to {default_path}." in result.output
    assert f"Saved to {named_path}." in result.output
    # the same menu keeps waiting after each save -- one prompt per line of input consumed
    assert result.output.count(PROMPT) == 4


def test_save_refuses_to_clobber_a_foreign_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    foreign = tmp_path / "foreign.txt"
    foreign.write_text("not a save", encoding="utf-8")

    result = _run(["run", str(MINI_PATH)], "save foreign.txt\nq\n")

    assert result.exit_code == 0
    assert f"Could not save: {foreign} exists and is not a ravel save" in result.output
    assert foreign.read_text(encoding="utf-8") == "not a save"


# --- (4) load/load FILE replaces the current game; a refused load leaves it running -------------


def test_load_command_replaces_the_current_game_and_shows_its_menu(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "save start.json\n2\nsave fork.json\nload start.json\nq\n")

    assert result.exit_code == 0
    # after "load start.json" the intro's menu is shown again, not the fork's
    tail = result.output.rsplit("Go right", 1)[-1]
    assert "1: Study the signpost" in tail


def test_load_command_with_a_refused_load_prints_the_error_and_current_game_continues(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "load missing.json\n2\nq\n")

    assert result.exit_code == 0
    assert "Could not load:" in result.output
    # the current (unloaded) game kept running: choosing 2 still reaches the fork's menu
    assert "1: Go left" in result.output
    assert "2: Go right" in result.output


# --- (5) --load FILE at startup resumes without re-applying givens; a bad file exits non-zero ---


def test_load_flag_resumes_at_the_saved_menu_with_no_given_reapplied(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    setup = _run(["run", str(MINI_PATH)], "2\nsave fork.json\nq\n")
    assert setup.exit_code == 0

    result = _run(["run", str(MINI_PATH), "--load", "fork.json"], "q\n")

    assert result.exit_code == 0
    assert "1: Go left" in result.output
    assert "2: Go right" in result.output
    # the intro menu (from a fresh new_game) is not re-shown
    assert "Study the signpost" not in result.output


def test_load_flag_with_a_corrupt_file_prints_error_and_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"not json")

    result = _run(["run", str(MINI_PATH), "--load", "bad.json"])

    assert result.exit_code == 1
    assert result.stderr.startswith("Error:")
    assert "Traceback" not in result.stderr


# --- (6) reaching "end" prints the outcome and exits 0; a dead end prints its own message -------


def test_reaching_end_prints_the_outcome_and_exits_zero_without_reprompting(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # begin::bridge -> follow-the-tunnel -> press-onward-into-the-dark: end: won
    result = _run(["run", str(MINI_PATH)], "3\n1\n1\n")

    assert result.exit_code == 0
    assert "*** The End (outcome: won) ***" in result.output
    # no further prompt is offered once halted
    assert result.output.count(PROMPT) == 3


def test_dead_end_prints_its_own_message(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # begin::fork -> go-right: Location = "Nowhere" matches no situation
    result = _run(["run", str(MINI_PATH)], "2\n2\n")

    assert result.exit_code == 0
    assert "*** The story has nowhere left to go. ***" in result.output


# --- (7) q / EOF / Ctrl-C exit cleanly; s shows qualities; help/? lists commands -----------------


def test_q_exits_cleanly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "q\n")

    assert result.exit_code == 0
    assert result.exception is None


def test_eof_exits_cleanly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "")  # no input at all -> EOFError from input()

    assert result.exit_code == 0
    assert result.exception is None
    assert "Traceback" not in result.output


def test_keyboard_interrupt_exits_cleanly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    real_input = builtins.input
    calls = {"n": 0}

    def fake_input(prompt=""):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt
        return real_input(prompt)

    monkeypatch.setattr(builtins, "input", fake_input)

    result = _run(["run", str(MINI_PATH)])

    assert result.exit_code == 0
    assert result.exception is None


def test_s_shows_qualities_sorted_with_repr_values(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "s\nq\n")

    assert result.exit_code == 0
    # CliRunner's non-tty stdin never locally echoes the typed "s", so it lands glued to the
    # prompt's own line (a harness artifact, not a rendering bug -- a real terminal's Enter
    # key puts each response on its own line); assert by substring + ordering instead of
    # `splitlines()` membership. Amended 2026-09-28 (ravel-8qa.5.5.2).
    assert "'Count' = 1" in result.output
    assert "'Location' = 'Fork'" in result.output
    count_index = result.output.index("'Count' = 1")
    location_index = result.output.index("'Location' = 'Fork'")
    assert count_index < location_index  # sorted


def test_help_and_question_mark_list_the_commands(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _run(["run", str(MINI_PATH)], "help\n?\nq\n")

    assert result.exit_code == 0
    for command in ("save", "load", "s", "help", "q"):
        assert command in result.output


# --- (8) --verbose narrates; --debug opens pdb.post_mortem() on an unexpected error --------------


def test_verbose_narrates_quality_changes_and_situation_entry_exit(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # The intro query merely offers matching top-level situations (no push occurs until a choice
    # is made -- see engine.py's ``query``/``enter``), so a choice must be taken before quitting
    # for a SituationEntered/SituationExited pair to actually narrate. Amended 2026-09-28
    # (ravel-8qa.5.5.2): the original "q\n"-only input never entered a location.
    result = _run(["--verbose", "run", str(MINI_PATH)], "1\nq\n")

    assert result.exit_code == 0
    assert "## " in result.output
    assert "was" in result.output and "now" in result.output
    assert "Entering" in result.output


def test_debug_opens_pdb_post_mortem_on_an_unexpected_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    bad_story = tmp_path / "bad-story"
    bad_story.mkdir()
    (bad_story / "begin.ravel").write_text(
        'given:\n  - Location = "X"\n\nbegin:\n  - when:\n      - Location = "X"\n  - [::: not valid ravel\n',
        encoding="utf-8",
    )

    spy = Mock()
    monkeypatch.setattr(pdb, "post_mortem", spy)

    result = _run(["--debug", "run", str(bad_story)])

    assert result.exit_code == 1
    spy.assert_called_once()
