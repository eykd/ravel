"""Acceptance test for US2 (specs/002-spec-compliance): constraints clamp results.

RED per ravel-h6v.5.2.1 -- expected to FAIL until the US2 Green leaves land. Plain pytest (PD-15):
drives the public loader and engine surfaces and asserts computed values AND kinds.
"""

from pathlib import Path
from typing import Any

import pytest

from ravel import engine
from ravel.engine.outputs import QualityChanged
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

pytestmark = pytest.mark.acceptance


def build_story(tmp_path: Path, source: str) -> Story:
    """Write ``source`` as a one-file story and compile it."""
    (tmp_path / "begin.ravel").write_text(source, encoding="utf-8")
    env = Environment(loader=FileSystemLoader(base_path=str(tmp_path)))
    return Story.from_rulebook(env.load())


def effect_story(tmp_path: Path, effect: str, givens: tuple[str, ...] = ()) -> Story:
    """A story with one choice whose effect is ``effect``."""
    given_lines = "".join(f"  - {g}\n" for g in ("Location = 'Start'", *givens))
    return build_story(
        tmp_path,
        f"given:\n{given_lines}\n"
        "start:\n"
        "  - when:\n"
        "      - Location = 'Start'\n"
        "  - Ready.\n"
        "  - choice:\n"
        "      - [Go]Going.\n"
        f"      - effect: {effect}\n",
    )


def play_effect(tmp_path: Path, effect: str, givens: tuple[str, ...] = ()) -> list[QualityChanged]:
    """Run the story's one choice and return the ``X`` quality changes it emits."""
    story = effect_story(tmp_path, effect, givens)
    entered = engine.choose(story, engine.start(story).state, "begin::start")
    step = engine.choose(story, entered.state, "begin::start::go")
    return [o for o in step.outputs if isinstance(o, QualityChanged) and o.name == "X"]


def new_values(changes: list[QualityChanged]) -> list[tuple[Any, type]]:
    """The ``(new, type(new))`` pairs of ``changes``."""
    return [(c.new, type(c.new)) for c in changes]


class TestConstraintsClampEffects:
    def test_min_clamps_a_decrease(self, tmp_path):
        """US2-AS1: X = 5: `X -= 10 min 0` -> 0."""
        changes = play_effect(tmp_path, "X -= 10 min 0", givens=("X = 5",))
        assert new_values(changes) == [(0, int)]

    def test_max_clamps_an_increase(self, tmp_path):
        """US2-AS2: X = 5: `X += 10 max 8` -> 8."""
        changes = play_effect(tmp_path, "X += 10 max 8", givens=("X = 5",))
        assert new_values(changes) == [(8, int)]

    def test_result_inside_the_bound_is_unchanged(self, tmp_path):
        """US2-AS3: X = 5: `X += 1 max 8` -> 6."""
        changes = play_effect(tmp_path, "X += 1 max 8", givens=("X = 5",))
        assert new_values(changes) == [(6, int)]

    def test_float_bound_gives_a_float_result(self, tmp_path):
        """Contract: X = 5: `X -= 10 min 0.0` -> 0.0 (the bound's kind)."""
        changes = play_effect(tmp_path, "X -= 10 min 0.0", givens=("X = 5",))
        assert new_values(changes) == [(0.0, float)]

    def test_plain_assignment_clamps_too(self, tmp_path):
        """Contract: X = 5: `X = 20 max 8` -> 8 (`=` clamps too)."""
        changes = play_effect(tmp_path, "X = 20 max 8", givens=("X = 5",))
        assert new_values(changes) == [(8, int)]

    def test_negative_bound_on_an_unset_quality(self, tmp_path):
        """Contract: X unset: `X -= 3 min -2` -> -2."""
        changes = play_effect(tmp_path, "X -= 3 min -2")
        assert new_values(changes) == [(-2, int)]

    def test_constraint_on_a_string_result_is_a_chained_engine_error(self, tmp_path):
        """Contract: Name = "Hi": `X = Name max 3` -> InvalidOperationError <- ConstraintError."""
        from ravel.engine.errors import InvalidOperationError
        from ravel.exceptions import ConstraintError

        story = effect_story(tmp_path, "X = Name max 3", givens=('Name = "Hi"',))
        entered = engine.choose(story, engine.start(story).state, "begin::start")
        with pytest.raises(InvalidOperationError) as excinfo:
            engine.choose(story, entered.state, "begin::start::go")
        assert isinstance(excinfo.value.__cause__, ConstraintError)


class TestConstraintsClampGivens:
    def test_given_with_max_starts_clamped(self, tmp_path):
        """US2-AS4: a `given:` holding `Gold = 50 max 20` -> `engine.start` emits QualityChanged("Gold", None, 20)."""
        story = build_story(
            tmp_path,
            "given:\n  - Gold = 50 max 20\n\nstart:\n  - when:\n      - Gold = 20\n  - Ready.\n"
            "  - choice:\n      - [Go]Going.\n",
        )
        step = engine.start(story)
        changes = [o for o in step.outputs if isinstance(o, QualityChanged) and o.name == "Gold"]
        assert changes == [QualityChanged("Gold", None, 20)]
        assert type(changes[0].new) is int
