"""Acceptance test for US6 (specs/002-spec-compliance): the spec can't drift again.

RED per ravel-h6v.5.6.1 -- expected to FAIL until the US6 Green leaves land. Plain pytest (PD-15).
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "docs" / "RAVEL_LANGUAGE_SPEC.md"
SCOPED_SECTIONS = ("4", "5", "6", "7", "9", "11.4")


@pytest.mark.xfail(strict=True, reason="US6 not yet implemented; remove when this scenario passes")
def test_us06_as1_every_scoped_spec_example_runs_and_passes() -> None:
    """US6-AS1: every example in sections 4-7, 9 and 11.4 is exercised and passes."""
    from tests.spec_examples import extract_examples, run_example

    examples = extract_examples(SPEC.read_text(encoding="utf-8"))

    def in_section(example_section: str, wanted: str) -> bool:
        return example_section == wanted or example_section.startswith(wanted + ".")

    for wanted in SCOPED_SECTIONS:
        assert any(in_section(e.section, wanted) for e in examples), f"no examples found in section {wanted}"
    for example in examples:
        run_example(example)


@pytest.mark.xfail(strict=True, reason="US6 not yet implemented; remove when this scenario passes")
def test_us06_as2_a_wrong_expected_result_fails_naming_the_example() -> None:
    """US6-AS2: editing one example to a wrong expected result fails a test naming that example."""
    from tests.spec_examples import extract_examples, run_example

    original = "10 - 4 - 2        → 4"
    text = SPEC.read_text(encoding="utf-8")
    assert original in text
    edited = text.replace(original, "10 - 4 - 2        → 8")

    matching = [e for e in extract_examples(edited) if "10 - 4 - 2" in e.text]
    assert matching, "the edited example was not extracted"
    with pytest.raises(AssertionError) as excinfo:
        run_example(matching[0])
    assert "10 - 4 - 2" in str(excinfo.value)
    assert "expected 8, got 4" in str(excinfo.value)
