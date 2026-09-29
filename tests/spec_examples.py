"""Extract and run the worked examples in ``docs/RAVEL_LANGUAGE_SPEC.md``."""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SpecExample:
    """One worked example line from the language spec."""

    section: str
    line: int
    text: str
    kind: Literal["result", "operation", "comparison"]


_HEADING = re.compile(r"^#{2,3}\s+(\d+(?:\.\d+)?)\.?(?:\s|$)")
_SCOPED_TOP = frozenset({"4", "5", "6", "7", "9"})
_KEY = re.compile(r"^([A-Za-z_]\w*):\s*(.*)$")
_ITEM = re.compile(r"^(\s*)-\s+(.*)$")
_TRAILING_COMMENT = re.compile(r"\s+#.*$")
_KEY_KINDS: dict[str, Literal["operation", "comparison"]] = {
    "given": "operation",
    "effect": "operation",
    "when": "comparison",
}


def _is_scoped(section: str | None) -> bool:
    """Say whether ``section`` (a heading number) holds examples that must run."""
    if section is None:
        return False
    return section.split(".")[0] in _SCOPED_TOP or section == "11.4"


def _result_text(line: str) -> str:
    """Return a result line with any trailing comment stripped from its expected literal."""
    left, _, right = line.partition(" → ")
    right = right.strip()
    quoted = re.match(r'"[^"]*"', right)
    literal = quoted.group(0) if quoted else re.split(r"\s{2,}|\s*\(", right, maxsplit=1)[0]
    return f"{left.strip()} → {literal}"


def _item_example(
    line: str,
    keys: list[tuple[int, str]],
) -> tuple[str, Literal["operation", "comparison"]] | None:
    """Classify a YAML list item, returning (text, kind) or None; may push an inline key."""
    match = _ITEM.match(line)
    if match is None:
        return None
    indent = len(match.group(1))
    rest = match.group(2)
    if rest.startswith("{") and "}" in rest:
        return rest[1 : rest.index("}")].strip(), "comparison"
    inline = _KEY.match(rest)
    if inline is not None:
        key, value = inline.group(1), _TRAILING_COMMENT.sub("", inline.group(2)).strip()
        key_indent = indent + 2
        while keys and keys[-1][0] >= key_indent:
            keys.pop()
        if not value:
            keys.append((key_indent, key))
        elif key in _KEY_KINDS:
            return value, _KEY_KINDS[key]
        return None
    while keys and keys[-1][0] > indent:
        keys.pop()
    if keys and keys[-1][1] in _KEY_KINDS:
        return _TRAILING_COMMENT.sub("", rest).strip(), _KEY_KINDS[keys[-1][1]]
    return None


def extract_examples(markdown: str) -> list[SpecExample]:
    """Return the scoped worked examples found in ``markdown``."""
    examples: list[SpecExample] = []
    section: str | None = None
    in_fence = False
    keys: list[tuple[int, str]] = []
    for number, line in enumerate(markdown.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            keys = []
            continue
        if not in_fence:
            if line.startswith("##") and not line.startswith("####"):
                heading = _HEADING.match(line)
                section = heading.group(1) if heading else None
            continue
        if not _is_scoped(section) or not line.strip():
            continue
        assert section is not None
        if " → " in line:
            examples.append(SpecExample(section, number, _result_text(line), "result"))
            continue
        found = _item_example(line, keys)
        if found is not None:
            examples.append(SpecExample(section, number, found[0], found[1]))
            continue
        key = _KEY.match(line.strip())
        if key is not None and not _ITEM.match(line):
            indent = len(line) - len(line.lstrip())
            while keys and keys[-1][0] >= indent:
                keys.pop()
            keys.append((indent, key.group(1)))
    return examples


def run_example(example: SpecExample) -> None:
    """Run ``example`` against the real implementation, raising AssertionError on mismatch."""
