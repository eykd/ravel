"""Acceptance test for US5 (specs/002-spec-compliance): the docs describe the shipped system.

RED per ravel-h6v.5.5.1 -- expected to FAIL until the US5 Green leaves land. Plain pytest (PD-15):
reads the language spec, the VM spec and CLAUDE.md as text, anchored on this file.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

ROOT = Path(__file__).resolve().parents[3]

OUTPUT_TYPES = (
    "TextShown",
    "ChoicesOffered",
    "QualityChanged",
    "SituationEntered",
    "SituationExited",
    "Halted",
    "StoryChanged",
)


def read(relative: str) -> str:
    """Return the UTF-8 text of the repo file at ``relative``."""
    return (ROOT / relative).read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """Return the body of the markdown section whose heading line starts with ``heading``."""
    match = re.search(rf"^#+ {re.escape(heading)}.*?(?=^#+ |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, f"missing section {heading!r}"
    return match.group(0)


def test_us05_as1_language_spec_is_v02() -> None:
    """US5-AS1: the language spec is v0.2, reflects R1-R8, has a precedence table, PEG matches code."""
    spec = read("docs/RAVEL_LANGUAGE_SPEC.md")

    assert re.search(r"^\*\*Version\*\*: 0\.2\b", spec, re.MULTILINE)
    history = section(spec, "14. Version History")
    assert re.search(r"\|\s*0\.2\s*\|\s*2026-09-28\s*\|", history)

    expressions = section(spec, "5.1")
    assert "Precedence" in expressions
    assert "Associativity" in expressions

    assert "Circular includes are allowed" in section(spec, "3.1")
    assert "A condition that cannot be evaluated" in section(spec, "6.3")
    assert "reserved inside expressions only" in section(spec, "4.1")
    choice_directive = section(spec, "9.2")
    assert "The bracketed line must be the choice's first item" in choice_directive
    assert "before its effects" not in choice_directive

    grammar = section(spec, "10.1")
    assert "identifier      = ~'(?!(?:value|min|max)\\b)[^\\W\\d]\\w*'" in grammar
    assert "additive          = multiplicative (ws? additive_op ws? multiplicative)*" in grammar


def test_us05_as2_vm_spec_is_v02() -> None:
    """US5-AS2: the VM spec is v0.2 and describes the shipped engine, with the design in Appendix A."""
    spec = read("docs/RAVEL_VM_SPEC.md")

    assert re.search(r"^\*\*Version\*\*: 0\.2\b", spec, re.MULTILINE)
    for name in ("start", "choose", "present", "resume"):
        assert re.search(rf"`{name}\(", spec), name
    for output in OUTPUT_TYPES:
        assert output in spec, output
    headings = re.findall(r"^#+ .*$", spec, re.MULTILINE)
    for recipe in ("Realtime", "Async", "HATEOAS"):
        assert any(recipe in heading for heading in headings), recipe
    assert any(heading.startswith("## Appendix A") for heading in headings)
    assert not re.search(r"^\| .*Expression.*\*\*Implemented\*\*", spec, re.MULTILINE)


def test_us05_as3_claude_md_matches_docs() -> None:
    """US5-AS3: CLAUDE.md's Language reference paragraph names both docs as v0.2."""
    claude = read("CLAUDE.md")
    paragraph = section(claude, "Language reference")

    assert "docs/RAVEL_LANGUAGE_SPEC.md" in paragraph
    assert "docs/RAVEL_VM_SPEC.md" in paragraph
    assert paragraph.count("v0.2") >= 2
    assert "predates the pure" not in paragraph
    assert "annotated 0.1" not in paragraph
    assert "instruction-set VM" not in paragraph
