"""US6-AS3: property test that save/load/continue matches an uninterrupted run (unchanged story).

Per ravel-8qa.5.6.2, specs/001-reentrant-vm/spec.md FR-032, FR-025, SC-003 (2026-09-28 revision:
FR-025's determinism law is now scoped to an UNCHANGED story), and
specs/001-reentrant-vm/contracts/save-format.md SS Round-trip laws.

Drives real Cloak playthroughs (``examples/cloak``) through ``ravel.app.session.GameSession`` and
the save codec: pick a random valid choice sequence (each step drawn by menu index, never by
location ID, so the property covers whatever the compiled rulebook actually offers), save at a
random split point via an in-memory dict-backed ``SaveStore`` fake (``tmp_path`` is a
function-scoped fixture and hypothesis rejects those under ``@given`` --
``HealthCheck.function_scoped_fixture``), load into a second, independently compiled ``Story`` of
Cloak, continue with the same remaining choices, and assert the continued run matches the
uninterrupted run byte-for-byte on the final state and output-for-output on every post-split step.
"""

from pathlib import Path
from typing import Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ravel.adapters.story_source import FileSystemStorySource
from ravel.app.saves import encode_save
from ravel.app.session import GameSession
from ravel.engine.outputs import Output, StoryChanged

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"

MAX_STEPS: Final = 100

# Compiled once, reused as the "unchanged" story on both sides of the uninterrupted run and the
# pre-split half of the interrupted run.
STORY_A: Final = FileSystemStorySource(CLOAK_PATH).load()


class DictSaveStore:
    """An in-memory ``SaveStore`` fake -- safe to use under ``@given`` (no filesystem fixture)."""

    def __init__(self) -> None:
        self._saves: dict[str, bytes] = {}

    def write(self, name: str, data: bytes) -> str:
        self._saves[name] = data
        return name

    def read(self, name: str) -> bytes:
        if name not in self._saves:
            raise FileNotFoundError(name)
        return self._saves[name]


@settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_save_load_continue_matches_uninterrupted_run(data: st.DataObject) -> None:
    # Uninterrupted run: play a random route by menu index (never by location ID, so the property
    # covers whatever the compiled rulebook actually offers), remembering each step's outputs and
    # the menu offered at each step, up to MAX_STEPS or a halt -- a prefix, including the empty
    # route or a route that reaches a halt, is a valid game and is never forced further.
    uninterrupted = GameSession(STORY_A, DictSaveStore())
    uninterrupted.new_game()
    route: list[str] = []
    menus_by_step: list[tuple[str, ...]] = []
    outputs_by_step: list[tuple[Output, ...]] = []
    for _ in range(MAX_STEPS):
        menu = uninterrupted.menu()
        if not menu:
            break
        index = data.draw(st.integers(min_value=0, max_value=len(menu) - 1))
        location = menu[index].location
        menus_by_step.append(tuple(choice.location for choice in menu))
        outputs_by_step.append(uninterrupted.choose(location))
        route.append(location)
    final_menu = tuple(choice.location for choice in uninterrupted.menu())

    split = data.draw(st.integers(min_value=0, max_value=len(route)))
    menu_at_split = menus_by_step[split] if split < len(menus_by_step) else final_menu

    # Interrupted run, first half: same story instance, save at the split.
    store = DictSaveStore()
    interrupted = GameSession(STORY_A, store)
    interrupted.new_game()
    for location in route[:split]:
        interrupted.choose(location)
    interrupted.save("mid.json")

    # Load into a second, independently compiled Story -- catches compile nondeterminism, and
    # since the story is unchanged the load must produce no StoryChanged output (FR-025).
    story_b = FileSystemStorySource(CLOAK_PATH).load()
    resumed = GameSession(story_b, store)
    load_outputs = resumed.load("mid.json")
    assert not any(isinstance(output, StoryChanged) for output in load_outputs)
    assert tuple(choice.location for choice in resumed.menu()) == menu_at_split

    # Continue with the same remaining choices; the per-step outputs must match the uninterrupted
    # run's outputs for the same steps. Frozen-attrs ``==`` has the same ``1 == 1.0`` blind spot
    # the save-format contract warns about, so compare via repr instead of bare ==.
    continued_outputs = [resumed.choose(location) for location in route[split:]]
    assert [repr(outputs) for outputs in continued_outputs] == [repr(outputs) for outputs in outputs_by_step[split:]]

    # The final state must round-trip identically, per the save-format contract's round-trip law
    # -- compared via encode_save bytes, not bare ==, since 1 == 1.0 in Python.
    assert encode_save(story_b, resumed.state) == encode_save(STORY_A, uninterrupted.state)
