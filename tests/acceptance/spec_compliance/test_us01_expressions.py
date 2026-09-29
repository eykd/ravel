"""Acceptance test for US1 (specs/002-spec-compliance): expressions compute what the spec says.

RED per ravel-h6v.5.1.1 -- expected to FAIL until the US1 Green leaves land. Plain pytest (PD-15):
drives the public parser, engine, and session surfaces and asserts computed values AND kinds.
"""

from pathlib import Path
from typing import Any

import pytest

from ravel import engine
from ravel.app import GameSession
from ravel.engine.outputs import Halted, QualityChanged, TextShown
from ravel.engine.state import Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader
from ravel.parsers import ComparisonParser, OperationParser

pytestmark = pytest.mark.acceptance


def run(src: str, qualities: dict[str, Any] | None = None) -> Any:
    """Parse the operation ``src`` and evaluate it against ``qualities``."""
    qualities = qualities or {}
    op = OperationParser().parse(src)
    return op.evaluate(qualities.get(op.quality), qualities=qualities)


def check(src: str, qualities: dict[str, Any] | None = None) -> Any:
    """Parse the comparison ``src`` and check it against ``qualities``."""
    return ComparisonParser().parse(src).check(qualities or {})


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


class TestArithmetic:
    def test_subtraction_is_left_associative(self):
        """US1-AS1: X = 10 - 4 - 2 -> 4."""
        result = run("X = 10 - 4 - 2")
        assert result == 4
        assert type(result) is int

    def test_division_and_precedence(self):
        """US1-AS2: 8 / 4 / 2 -> 1.0; 2 + 3 * 4 -> 14; 7 // 2 * 2 -> 6 (one tier)."""
        halved = run("X = 8 / 4 / 2")
        assert halved == 1.0
        assert type(halved) is float
        mixed = run("X = 2 + 3 * 4")
        assert mixed == 14
        assert type(mixed) is int
        same_tier = run("X = 7 // 2 * 2")
        assert same_tier == 6
        assert type(same_tier) is int

    def test_negative_literals(self):
        """US1-AS3: X = -5 -> -5; `Health > -1` parses and holds on empty qualities; X = -1.5."""
        five = run("X = -5")
        assert five == -5
        assert type(five) is int
        assert check("Health > -1") is True
        frac = run("X = -1.5")
        assert frac == -1.5
        assert type(frac) is float

    def test_empty_string_literal(self):
        """US1-AS4: X = "" -> ""."""
        result = run('X = ""')
        assert result == ""
        assert type(result) is str

    def test_string_equality_comparison(self):
        """US1-AS8: Name == "Wearing Cloak" is true when Name is "Wearing Cloak"."""
        assert check('Name == "Wearing Cloak"', {"Name": "Wearing Cloak"}) is True

    def test_unset_quality_in_expression_is_zero(self):
        """US1-AS6 (parser level): X = Health + 1 with Health unset -> 1."""
        result = run("X = Health + 1")
        assert result == 1
        assert type(result) is int


class TestEngineExpressions:
    def test_bracketed_and_bare_quality_refs_in_given(self, tmp_path):
        """US1-AS5: Health = 7, Bonus = 3: X = [Health] + Bonus -> 10."""
        story = build_story(
            tmp_path,
            "given:\n  - Health = 7\n  - Bonus = 3\n  - X = [Health] + Bonus\n\n"
            "start:\n  - when:\n      - Health = 7\n  - choice:\n      - [Go]Going.\n",
        )
        step = engine.start(story)
        changes = [o for o in step.outputs if isinstance(o, QualityChanged) and o.name == "X"]
        assert [(c.new, type(c.new)) for c in changes] == [(10, int)]

    def test_unset_quality_ref_reads_zero_in_given(self, tmp_path):
        """US1-AS6: Health unset: X = Health + 1 -> 1."""
        story = build_story(
            tmp_path,
            "given:\n  - X = Health + 1\n\n"
            "start:\n  - when:\n      - X = 1\n  - Ready.\n  - choice:\n      - [Go]Going.\n",
        )
        step = engine.start(story)
        changes = [o for o in step.outputs if isinstance(o, QualityChanged) and o.name == "X"]
        assert [(c.new, type(c.new)) for c in changes] == [(1, int)]

    def test_value_is_current_quality_in_effect(self, tmp_path):
        """US1-AS7: X = 10: X += value * 2 -> 30."""
        story = effect_story(tmp_path, "X += value * 2", givens=("X = 10",))
        start = engine.start(story)
        entered = engine.choose(story, start.state, "begin::start")
        step = engine.choose(story, entered.state, "begin::start::go")
        changes = [o for o in step.outputs if isinstance(o, QualityChanged) and o.name == "X"]
        assert [(c.new, type(c.new)) for c in changes] == [(30, int)]


class TestEvaluationFailures:
    def test_zero_division_in_effect_is_a_chained_engine_error(self, tmp_path):
        """RT-1: X = 100 / Bonus (Bonus unset) -> InvalidOperationError <- EvaluationError <- ZeroDivisionError."""
        from ravel.engine.errors import InvalidOperationError
        from ravel.exceptions import EvaluationError

        story = effect_story(tmp_path, "X = 100 / Bonus")
        entered = engine.choose(story, engine.start(story).state, "begin::start")
        with pytest.raises(InvalidOperationError) as excinfo:
            engine.choose(story, entered.state, "begin::start::go")
        assert isinstance(excinfo.value.__cause__, EvaluationError)
        assert isinstance(excinfo.value.__cause__.__cause__, ZeroDivisionError)

    def test_type_error_in_effect_is_a_chained_engine_error(self, tmp_path):
        """RT-1: X = Name + 1 with Name = "a" -> InvalidOperationError <- EvaluationError <- TypeError."""
        from ravel.engine.errors import InvalidOperationError
        from ravel.exceptions import EvaluationError

        story = effect_story(tmp_path, "X = Name + 1", givens=('Name = "a"',))
        entered = engine.choose(story, engine.start(story).state, "begin::start")
        with pytest.raises(InvalidOperationError) as excinfo:
            engine.choose(story, entered.state, "begin::start::go")
        assert isinstance(excinfo.value.__cause__, EvaluationError)
        assert isinstance(excinfo.value.__cause__.__cause__, TypeError)

    @pytest.mark.parametrize(
        ("effect", "givens"),
        [("X = 100 / Bonus", ()), ("X = Name + 1", ('Name = "a"',))],
    )
    def test_session_keeps_previous_state_after_a_failed_choice(self, tmp_path, effect, givens):
        """RT-1: a GameSession keeps its previous state after an evaluation failure."""
        from ravel.engine.errors import InvalidOperationError

        class NoSaves:
            def write(self, name: str, data: bytes) -> str:
                raise NotImplementedError

            def read(self, name: str) -> bytes:
                raise FileNotFoundError(name)

        session = GameSession(effect_story(tmp_path, effect, givens), NoSaves())
        session.new_game()
        session.choose("begin::start")
        before = session.state
        with pytest.raises(InvalidOperationError):
            session.choose("begin::start::go")
        assert session.state == before

    def test_failing_when_predicate_does_not_offer_the_rule(self, tmp_path):
        """RT-2: `when: X > 10 / Y` (Y unset) is not offered; another matching rule is."""
        story = build_story(
            tmp_path,
            "given:\n  - X = 2\n  - Name = 'a'\n\n"
            "broken:\n  - when:\n      - X > 10 / Y\n  - choice:\n      - [Broken]Broken.\n\n"
            "typed:\n  - when:\n      - X > Name\n  - choice:\n      - [Typed]Typed.\n\n"
            "fine:\n  - when:\n      - X = 2\n  - choice:\n      - [Fine]Fine.\n",
        )
        step = engine.start(story)
        offered = [c.location for o in step.outputs if hasattr(o, "choices") for c in o.choices]
        assert offered == ["begin::fine"]

    def test_failing_line_predicate_hides_the_line(self, tmp_path):
        """RT-10: `{Health > 10 / Y}Hidden.` (Y unset) shows no text and play continues."""
        story = build_story(
            tmp_path,
            "given:\n  - Health = 5\n\n"
            "start:\n  - when:\n      - Health = 5\n  - '{Health > 10 / Y}Hidden.'\n"
            "  - Visible.\n  - choice:\n      - [Go]Going.\n",
        )
        step = engine.start(story)
        texts = [o.text for o in step.outputs if isinstance(o, TextShown)]
        assert "Hidden." not in texts
        assert "Visible." in texts
        assert step.state.status is Status.WAITING

    def test_failing_common_predicate_halts_without_raising(self, tmp_path):
        """RT-14: a top-level `when: X > 10 / Y` (Y unset) guarding the only situation halts the game."""
        story = build_story(
            tmp_path,
            "given:\n  - X = 2\n\nwhen:\n  - X > 10 / Y\n\nstart:\n  - Only.\n  - choice:\n      - [Go]Going.\n",
        )
        step = engine.start(story)
        assert Halted("", True) in step.outputs
        assert step.state.status is Status.HALTED
