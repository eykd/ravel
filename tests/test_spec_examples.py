"""Unit tests for the spec-example extractor (specs/002-spec-compliance/contracts/spec-examples.md)."""

from collections import Counter
from pathlib import Path

import pytest

from tests.spec_examples import SpecExample, extract_examples, run_example


def fenced(*lines: str, info: str = "") -> str:
    """Build a fenced code block from ``lines``."""
    return "\n".join([f"```{info}", *lines, "```"])


def doc(heading: str, *lines: str, info: str = "") -> str:
    """Build a markdown document with one heading and one fenced block."""
    return f"{heading}\n\nSome prose.\n\n{fenced(*lines, info=info)}\n"


def summarize(examples: list[SpecExample]) -> list[tuple[str, str, str]]:
    """Reduce examples to (section, whitespace-normalized text, kind)."""
    return [(e.section, " ".join(e.text.split()), e.kind) for e in examples]


def test_result_line_is_a_result_example() -> None:
    examples = extract_examples(doc("## 5. Expressions", "10 - 4 - 2        → 4"))

    assert summarize(examples) == [("5", "10 - 4 - 2 → 4", "result")]


def test_result_line_comment_after_two_spaces_is_stripped() -> None:
    examples = extract_examples(doc("## 5. Expressions", "2 + 3 * 4 → 14  (multiplication first)"))

    assert summarize(examples) == [("5", "2 + 3 * 4 → 14", "result")]


def test_result_line_records_one_based_line_number() -> None:
    markdown = doc("## 5. Expressions", "1 + 1 → 2", "2 + 2 → 4")

    assert [e.line for e in extract_examples(markdown)] == [6, 7]


def test_fence_with_or_without_info_string_is_scanned() -> None:
    plain = extract_examples(doc("## 4. Values", "1 + 1 → 2"))
    yaml = extract_examples(doc("## 4. Values", "1 + 1 → 2", info="yaml"))

    assert len(plain) == 1
    assert len(yaml) == 1


def test_scoped_sections_are_scanned() -> None:
    for heading, section in [
        ("## 4. A", "4"),
        ("## 5. B", "5"),
        ("## 6. C", "6"),
        ("## 7. D", "7"),
        ("## 9. E", "9"),
        ("### 11.4 F", "11.4"),
    ]:
        markdown = f"## 11. Appendix\n\n{doc(heading, '1 + 1 → 2')}"
        assert [e.section for e in extract_examples(markdown)] == [section]


def test_unscoped_sections_are_ignored() -> None:
    for heading in ["## 3. Intro", "## 8. Other", "### 10.1 Grammar", "## 12. Cloak", "## Appendix A", "### 11.3 X"]:
        assert extract_examples(doc(heading, "1 + 1 → 2")) == []


def test_operation_under_given_key_is_an_operation_example() -> None:
    examples = extract_examples(doc("## 6. Rules", "given:", "  - Health = 10"))

    assert summarize(examples) == [("6", "Health = 10", "operation")]


def test_operation_under_effect_key_strips_trailing_comment() -> None:
    examples = extract_examples(doc("## 7. Effects", "effect:", "  - Health -= 10 min 0       # Cannot go below 0"))

    assert summarize(examples) == [("7", "Health -= 10 min 0", "operation")]


def test_effect_list_item_key_is_an_operation_example() -> None:
    examples = extract_examples(doc("## 7. Effects", "- effect: Gold += 5"))

    assert [e.kind for e in examples] == ["operation"]


def test_list_item_under_when_key_is_a_comparison_example() -> None:
    examples = extract_examples(doc("## 6. Rules", "when:", "  - Health > 3"))

    assert summarize(examples) == [("6", "Health > 3", "comparison")]


def test_brace_prefix_at_start_of_list_item_is_a_comparison_example() -> None:
    examples = extract_examples(doc("## 7. Effects", "- {Health > 3} You feel fine."))

    assert [e.kind for e in examples] == ["comparison"]


def test_bare_list_item_without_enclosing_key_is_ignored() -> None:
    assert extract_examples(doc("## 7. Effects", "- Health = 10")) == []


def test_last_enclosing_key_decides_classification() -> None:
    examples = extract_examples(doc("## 6. Rules", "when:", "  - Health > 3", "given:", "  - Health = 10"))

    assert [e.kind for e in examples] == ["comparison", "operation"]


def test_prose_text_directives_and_blank_lines_are_ignored() -> None:
    lines = ("Situation: Foyer", "", "  You are in the foyer.", "# just a comment")

    assert extract_examples(doc("## 5. Expressions", *lines)) == []


def test_prose_outside_fences_is_ignored() -> None:
    markdown = "## 5. Expressions\n\n1 + 1 → 2\n\n- Health = 10\n"

    assert extract_examples(markdown) == []


def test_line_number_counts_from_top_of_document() -> None:
    markdown = doc("## 7. Effects", "effect:", "  - Health = 10")

    assert [e.line for e in extract_examples(markdown)] == [7]


def test_run_example_wrong_result_raises_naming_example_and_expected_vs_got() -> None:
    example = SpecExample(section="5", line=1, text="1 + 1 → 3", kind="result")

    with pytest.raises(AssertionError, match=r"(?s)1 \+ 1 → 3.*expected 3, got 2"):
        run_example(example)


SPEC_PATH = Path(__file__).resolve().parent.parent / "docs" / "RAVEL_LANGUAGE_SPEC.md"
SPEC_EXAMPLES = extract_examples(SPEC_PATH.read_text(encoding="utf-8"))

EXPECTED_COUNTS = {
    "4.1": 1,
    "4.3": 3,
    "5.1": 10,
    "6.2": 5,
    "6.3": 2,
    "7.2": 4,
    "7.3": 6,
    "9.1": 5,
    "9.2": 5,
    "9.3": 3,
    "9.4": 2,
    "11.4": 3,
}


def example_id(example: SpecExample) -> str:
    """Name an example by section, line and text so a failure identifies it."""
    return f"\u00a7{example.section}:{example.line}: {' '.join(example.text.split())}"


@pytest.mark.parametrize("example", SPEC_EXAMPLES, ids=example_id)
def test_spec_example(example: SpecExample) -> None:
    run_example(example)


def test_extraction_counts() -> None:
    assert dict(Counter(e.section for e in SPEC_EXAMPLES)) == EXPECTED_COUNTS
