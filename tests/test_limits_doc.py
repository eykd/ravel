"""The "### E. Limits" table in the language spec must state exactly the caps the code enforces."""

import re
import sys
from pathlib import Path

import pytest

from ravel import parsers, types
from ravel.app import saves
from ravel.compiler import directives
from ravel.engine import state
from ravel.environments import MAX_INLINE_LIST_MARKERS, MAX_RULEBOOK_BYTES, MAX_SOURCE_NESTING_DEPTH

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024

# (start of the Limit cell, the value the code enforces), one entry per table row, in table order.
DOCUMENTED_LIMITS: list[tuple[str, int | range]] = [
    ("Operands in one expression chain", parsers.MAX_EXPRESSION_OPERANDS),
    ("Text length of one expression", parsers.MAX_EXPRESSION_LENGTH),
    ("Parenthesis nesting", parsers.MAX_PAREN_DEPTH),
    ("Total expression tree depth", parsers.MAX_EXPRESSION_DEPTH),
    ("Digits in an integer literal", sys.get_int_max_str_digits()),
    ("Indentation nesting", MAX_SOURCE_NESTING_DEPTH),
    ("Inline `- ` list markers", MAX_INLINE_LIST_MARKERS),
    ("Choice block nesting", directives.MAX_CHOICE_NESTING_DEPTH),
    ("String length", types.MAX_STRING_LENGTH),
    ("Integer quality range", state.INT_QUALITY_RANGE),
    ("Save file size", saves.MAX_SAVE_BYTES),
    ("Rulebook source size", MAX_RULEBOOK_BYTES),
]


def limits_rows() -> list[tuple[str, str]]:
    """Return the (Limit, Value) cells of every data row in the E. Limits table."""
    text = (ROOT / "docs/RAVEL_LANGUAGE_SPEC.md").read_text(encoding="utf-8")
    body = text.split("### E. Limits", 1)[1].split("\n---", 1)[0]
    rows = [line for line in body.splitlines() if line.startswith("|")][2:]
    return [(cells[0], cells[1]) for cells in (tuple(c.strip() for c in row.strip("|").split("|")) for row in rows)]


def parse_value(cell: str) -> int | range:
    """Parse a documented value: ``65,536``, ``4300 (...)``, ``1 MiB (...)`` or ``-2^63 to 2^63 - 1``."""
    if match := re.match(r"-2\^(\d+) to 2\^(\d+) - 1$", cell):
        return range(-(2 ** int(match[1])), 2 ** int(match[2]))
    if match := re.match(r"(\d+) MiB\b", cell):
        return int(match[1]) * MIB
    if match := re.match(r"[\d,]+", cell):
        return int(match[0].replace(",", ""))
    raise AssertionError(f"unparseable limit value {cell!r}")


def test_every_limit_row_is_bound_to_a_constant() -> None:
    """A new cap cannot land undocumented, and a documented row cannot lack a constant."""
    rows = limits_rows()
    assert len(rows) == len(DOCUMENTED_LIMITS)
    for (label, _), (prefix, _expected) in zip(rows, DOCUMENTED_LIMITS, strict=True):
        assert label.startswith(prefix)


@pytest.mark.parametrize(("prefix", "expected"), DOCUMENTED_LIMITS, ids=[p for p, _ in DOCUMENTED_LIMITS])
def test_documented_value_equals_constant(prefix: str, expected: int | range) -> None:
    """Each row's Value cell renders the constant the code enforces."""
    (value,) = [value for label, value in limits_rows() if label.startswith(prefix)]
    assert parse_value(value) == expected


def test_documented_rulebook_bytes_and_prefix_window() -> None:
    """The literal byte count and the text-line prefix window match their constants."""
    rows = dict(limits_rows())
    (rulebook,) = [v for k, v in rows.items() if k.startswith("Rulebook source size")]
    assert f"{MAX_RULEBOOK_BYTES:,} bytes" in rulebook
    (text_length,) = [k for k in rows if k.startswith("Text length of one expression")]
    assert f"first {parsers.MAX_EXPRESSION_LENGTH + 2:,} characters" in text_length


def test_vm_spec_points_at_limits_table_without_restating_it() -> None:
    """The VM spec defers to E. Limits instead of enumerating caps that can go stale."""
    text = (ROOT / "docs/RAVEL_VM_SPEC.md").read_text(encoding="utf-8")
    paragraph = text.split("**Story sources are trusted input.**", 1)[1].split("\n\n")[0]
    assert '"### E. Limits"' in paragraph
    assert "operand count" not in paragraph
