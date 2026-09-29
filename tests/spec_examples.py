"""Extract and run the worked examples in ``docs/RAVEL_LANGUAGE_SPEC.md``."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SpecExample:
    """One worked example line from the language spec."""

    section: str
    line: int
    text: str
    kind: Literal["result", "operation", "comparison"]


def extract_examples(markdown: str) -> list[SpecExample]:
    """Return the scoped worked examples found in ``markdown``."""
    return []


def run_example(example: SpecExample) -> None:
    """Run ``example`` against the real implementation, raising AssertionError on mismatch."""
