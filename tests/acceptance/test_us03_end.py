"""Acceptance test for US3: a story can end.

RED per ravel-8qa.5.3.1 -- expected to FAIL until the ``end`` directive
compiles and the engine halts on it (ravel-8qa.5.3.2, US3 Green). The mini
fixture's ``end:`` lines don't compile yet (``ParseError`` at load), and
Cloak's win/loss routes have no ``end:`` directive yet (missing halt, so the
menu re-offers instead), both of which turn these assertions RED today.
"""

import re
from pathlib import Path

import pytest

from ravel import engine
from ravel.engine.outputs import ChoicesOffered, Halted, QualityChanged, TextShown
from ravel.engine.state import Outcome, Status
from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLOAK_PATH = REPO_ROOT / "examples" / "cloak"
MINI_PATH = REPO_ROOT / "tests" / "fixtures" / "stories" / "mini"
LANGUAGE_SPEC_PATH = REPO_ROOT / "docs" / "RAVEL_LANGUAGE_SPEC.md"


def _load_story(path: Path) -> Story:
    return Story.from_rulebook(Environment(loader=FileSystemLoader(base_path=str(path))).load())


def test_end_halts_immediately_at_any_stack_depth_and_runs_nothing_after():
    """US3-AS1: ``end: <outcome>`` halts at any stack depth; nothing after it runs."""
    mini = _load_story(MINI_PATH)

    s0 = engine.start(mini)
    s1 = engine.choose(mini, s0.state, "begin::bridge")
    s2 = engine.choose(mini, s1.state, "begin::bridge::follow-the-tunnel")
    s3 = engine.choose(mini, s2.state, "begin::bridge::follow-the-tunnel::press-onward-into-the-dark")

    assert s3.state.status is Status.HALTED
    assert s3.state.outcome == Outcome("won", dead_end=False)
    assert s3.state.stack == ()
    assert s3.state.offered == ()
    # The "effect: Trap = 1" line after "end: won" never ran.
    assert not any(isinstance(output, QualityChanged) and output.name == "Trap" for output in s3.outputs)
    # No SituationExited/gather from the parent "bridge" situation ran either: no menu, no halt output
    # for anything but this one halt.
    assert not any(isinstance(output, ChoicesOffered) for output in s3.outputs)
    assert s3.outputs[-1] == Halted("won", False)


def test_bare_end_halts_with_empty_outcome():
    """US3-AS2: a bare ``end:`` halts with outcome ``""``."""
    mini = _load_story(MINI_PATH)

    s0 = engine.start(mini)
    s1 = engine.choose(mini, s0.state, "begin::bridge")
    s2 = engine.choose(mini, s1.state, "begin::bridge::follow-the-tunnel")
    s3 = engine.choose(mini, s2.state, "begin::bridge::follow-the-tunnel::turn-back-to-the-bridge")

    assert s3.state.status is Status.HALTED
    assert s3.state.outcome == Outcome("", dead_end=False)
    assert s3.state.stack == ()
    assert s3.state.offered == ()
    assert s3.outputs[-1] == Halted("", False)


def test_end_inside_a_choice_body_halts_from_inside_the_sub_situation():
    """US3-AS3: an ``end:`` inside a ``choice:`` body halts from inside the sub-situation."""
    mini = _load_story(MINI_PATH)

    s0 = engine.start(mini)
    s1 = engine.choose(mini, s0.state, "begin::bridge")
    s2 = engine.choose(mini, s1.state, "begin::bridge::shout-into-the-void")

    assert s2.state.status is Status.HALTED
    assert s2.state.outcome == Outcome("lost", dead_end=False)
    assert s2.state.stack == ()
    assert s2.state.offered == ()
    assert s2.outputs[-1] == Halted("lost", False)


def _walk_to_bar(cloak: Story, *, wearing_cloak: bool):
    """Drive Cloak from the intro to the Bar, ending with or without the cloak worn."""
    step = engine.start(cloak)
    step = engine.choose(cloak, step.state, "begin::intro")
    step = engine.choose(cloak, step.state, "begin::intro::press-onward")  # -> Foyer

    if not wearing_cloak:
        step = engine.choose(cloak, step.state, "foyer::cloakroom")
        step = engine.choose(cloak, step.state, "cloakroom::look")
        step = engine.choose(cloak, step.state, "cloakroom::look")
        step = engine.choose(cloak, step.state, "cloakroom::look")  # Cloakroom == 3
        step = engine.choose(cloak, step.state, "cloakroom::hang-up-cloak")  # Wearing Cloak = 0
        step = engine.choose(cloak, step.state, "cloakroom::leave")  # -> Foyer

    step = engine.choose(cloak, step.state, "foyer::bar")  # -> Bar
    return step


def test_cloak_winning_route_shows_the_win_message_and_halts_won():
    """US3-AS4/FR-019: playing Cloak to the intact message halts with outcome ``won``."""
    cloak = _load_story(CLOAK_PATH)

    step = _walk_to_bar(cloak, wearing_cloak=False)
    step = engine.choose(cloak, step.state, "bar-light::look")
    step = engine.choose(cloak, step.state, "bar-light::look")  # Bar == 2, Fumbled == 0
    step = engine.choose(cloak, step.state, "bar-light::look-at-message")

    assert any(isinstance(output, TextShown) and "**You have won**" in output.text for output in step.outputs)
    assert step.state.status is Status.HALTED
    assert step.state.outcome == Outcome("won", dead_end=False)
    assert step.outputs[-1] == Halted("won", False)


def test_cloak_losing_route_shows_the_scrambled_message_and_halts_lost():
    """US3-AS5/FR-019: playing Cloak to the scrambled message halts with outcome ``lost``."""
    cloak = _load_story(CLOAK_PATH)

    # Fumble in the dark bar first (Wearing Cloak == 1), then remove the cloak and return to a
    # now-lit bar: Fumbled and Bar are ordinary qualities, so both persist across the visit.
    step = _walk_to_bar(cloak, wearing_cloak=True)
    step = engine.choose(cloak, step.state, "bar-dark::look-in-dark")
    step = engine.choose(cloak, step.state, "bar-dark::look-in-dark")  # Bar == 2
    step = engine.choose(cloak, step.state, "bar-dark::fumble-around")  # Fumbled = 1
    step = engine.choose(cloak, step.state, "bar-dark::leave")  # -> Foyer, still wearing cloak
    step = engine.choose(cloak, step.state, "foyer::cloakroom")
    step = engine.choose(cloak, step.state, "cloakroom::look")
    step = engine.choose(cloak, step.state, "cloakroom::look")
    step = engine.choose(cloak, step.state, "cloakroom::look")  # Cloakroom == 3
    step = engine.choose(cloak, step.state, "cloakroom::hang-up-cloak")  # Wearing Cloak = 0
    step = engine.choose(cloak, step.state, "cloakroom::leave")  # -> Foyer
    step = engine.choose(cloak, step.state, "foyer::bar")  # -> lit Bar, Fumbled == 1, Bar == 2
    step = engine.choose(cloak, step.state, "bar-light::look-at-scrambled-message")

    assert any(isinstance(output, TextShown) and "**Y… …ve …n**" in output.text for output in step.outputs)
    assert step.state.status is Status.HALTED
    assert step.state.outcome == Outcome("lost", dead_end=False)
    assert step.outputs[-1] == Halted("lost", False)


def _section(spec_text: str, heading_pattern: str) -> str:
    """Slice ``spec_text`` from a heading matching ``heading_pattern`` to the next same-or-higher heading."""
    lines = spec_text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match and re.search(heading_pattern, match.group(2)):
            start = index
            level = len(match.group(1))
            break
    assert start is not None, f"heading matching {heading_pattern!r} not found"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


_END_MENTION = re.compile(r"`end`|- end:")


def test_language_spec_documents_end_in_directives_yaml_and_execution_sections():
    """US3-AS6: the language spec documents ``end`` under SS9, SS10.2, and SS11.2."""
    spec_text = LANGUAGE_SPEC_PATH.read_text(encoding="utf-8")

    directives_section = _section(spec_text, r"^9\. Directives")
    yaml_structure_section = _section(spec_text, r"^10\.2 YAML Structure")
    execution_section = _section(spec_text, r"^11\.2 Situation Execution")

    assert _END_MENTION.search(directives_section), "SS9 (Directives) doesn't document `end`"
    assert _END_MENTION.search(yaml_structure_section), "SS10.2 (YAML structure) doesn't document `end`"
    assert _END_MENTION.search(execution_section), "SS11.2 (Execution model) doesn't document `end`"
