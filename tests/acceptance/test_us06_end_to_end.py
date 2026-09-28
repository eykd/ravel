"""Acceptance test for US6: prove Cloak plays end to end, plus a CLI transcript across a save/load.

RED per ravel-8qa.5.6.1. Per specs/001-reentrant-vm/spec.md SS US-6 AS1, AS2, AS4 (AS3, the
hypothesis-driven determinism property, is ravel-8qa.5.6.2's job -- not written here).

(1) and (2) drive ``ravel.app.session.GameSession`` directly, choosing by location ID -- never by
menu position -- to pin the exact win and loss routes through Cloak. (3) drives the real
``ravel.cli`` front door (a ``click.testing.CliRunner`` over ``ConsoleUI``) through a save mid-route,
a quit, and a ``--load`` restart, and asserts the transcript ends on the win outcome line. Per US5
(ravel-8qa.5.5.x), ``ravel.cli`` is a thin ``ConsoleUI`` over ``GameSession``; ``ravel.vm`` and
blinker are gone.

Given US2/US3/US4/US5 are already closed, both routes below are expected to already reach their
documented halts -- if so this file is unexpectedly GREEN already; see the task's commit
instructions for that case.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

import ravel.cli as cli
from ravel.adapters.save_store import FileSaveStore
from ravel.adapters.story_source import FileSystemStorySource
from ravel.app import GameSession
from ravel.engine.outputs import Halted
from ravel.engine.state import Outcome, Status

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"

# US6-AS1: the exact win route, by location ID.
WIN_ROUTE = (
    "begin::intro",
    "begin::intro::press-onward",
    "foyer::cloakroom",
    "cloakroom::look",
    "cloakroom::look",
    "cloakroom::the-hook",
    "cloakroom::hang-up-cloak",
    "cloakroom::leave",
    "foyer::bar",
    "bar-light::look",
    "bar-light::look",
    "bar-light::look-at-message",
)

# US6-AS2: the exact loss route, by location ID.
LOSS_ROUTE = (
    "begin::intro",
    "begin::intro::press-onward",
    "foyer::bar",
    "bar-dark::look-in-dark",
    "bar-dark::look-in-dark",
    "bar-dark::fumble-around",
    "bar-dark::leave",
    "foyer::cloakroom",
    "cloakroom::look",
    "cloakroom::look",
    "cloakroom::the-hook",
    "cloakroom::hang-up-cloak",
    "cloakroom::leave",
    "foyer::bar",
    "bar-light::look-at-scrambled-message",
)


def _cloak_session(tmp_path: Path) -> GameSession:
    story = FileSystemStorySource(CLOAK_PATH).load()
    return GameSession(story, FileSaveStore(tmp_path))


def test_cloak_win_route_by_location_id_halts_won(tmp_path):
    """US6-AS1: driving the exact win route by location ID halts with outcome ``won``."""
    session = _cloak_session(tmp_path)
    session.new_game()

    outputs = ()
    for location in WIN_ROUTE:
        outputs = session.choose(location)

    assert session.state.status is Status.HALTED
    assert session.state.outcome == Outcome("won", dead_end=False)
    assert outputs[-1] == Halted("won", False)


def test_cloak_loss_route_by_location_id_halts_lost(tmp_path):
    """US6-AS2: driving the exact loss route by location ID halts with outcome ``lost``."""
    session = _cloak_session(tmp_path)
    session.new_game()

    outputs = ()
    for location in LOSS_ROUTE:
        outputs = session.choose(location)

    assert session.state.status is Status.HALTED
    assert session.state.outcome == Outcome("lost", dead_end=False)
    assert outputs[-1] == Halted("lost", False)


def _menu_numbers_for(route: tuple[str, ...], tmp_path: Path) -> list[int]:
    """The 1-based menu position that selects each location in ``route``, in order.

    Computed against a fresh session driven the same way the assertions above drive it, so the
    CLI transcript test below never hardcodes menu ordering -- only the location-ID route does.
    """
    session = _cloak_session(tmp_path)
    session.new_game()
    numbers = []
    for location in route:
        choices = session.menu()
        index = next(position for position, choice in enumerate(choices, start=1) if choice.location == location)
        numbers.append(index)
        session.choose(location)
    return numbers


def _run(args, input_text=None):
    runner = CliRunner()
    return runner.invoke(cli.main, args, input=input_text)


def test_cli_transcript_saves_mid_route_and_finishes_the_win_route_after_reload(monkeypatch, tmp_path):
    """US6-AS4: a CLI transcript plays the win route across a save, a quit, and a ``--load`` restart."""
    monkeypatch.chdir(tmp_path)
    numbers = _menu_numbers_for(WIN_ROUTE, tmp_path)
    split = 6  # after cloakroom::the-hook, well short of the win halt

    first_input = "\n".join(str(number) for number in numbers[:split]) + "\nsave mid.json\nq\n"
    first_result = _run(["run", str(CLOAK_PATH)], first_input)

    assert first_result.exit_code == 0
    assert "Saved to" in first_result.output
    assert (tmp_path / "mid.json").exists()
    # the game hadn't halted yet -- no outcome line in the first transcript
    assert "*** The End" not in first_result.output

    second_input = "\n".join(str(number) for number in numbers[split:]) + "\n"
    second_result = _run(["run", str(CLOAK_PATH), "--load", "mid.json"], second_input)

    assert second_result.exit_code == 0
    transcript_lines = second_result.output.rstrip("\n").splitlines()
    assert transcript_lines[-1] == "*** The End (outcome: won) ***"
