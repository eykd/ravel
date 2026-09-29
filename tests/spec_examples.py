"""Extract and run the worked examples in ``docs/RAVEL_LANGUAGE_SPEC.md``."""

import re
from dataclasses import dataclass
from typing import Literal

from ravel import exceptions, parsers, types
from ravel.types import QualityValue


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


def _pop_keys_from(keys: list[tuple[int, str]], indent: int) -> None:
    """Drop every tracked YAML key indented at ``indent`` or deeper."""
    while keys and keys[-1][0] >= indent:
        keys.pop()


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
        _pop_keys_from(keys, key_indent)
        if not value:
            keys.append((key_indent, key))
        elif key in _KEY_KINDS:
            return value, _KEY_KINDS[key]
        return None
    _pop_keys_from(keys, indent + 1)
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
            _pop_keys_from(keys, indent)
            keys.append((indent, key.group(1)))
    return examples


def _parse_literal(text: str) -> QualityValue | bool:
    """Parse an expected-result literal: a quoted string, ``true``/``false``, an int or a float."""
    if text in ("true", "false"):
        return text == "true"
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        return float(text)


def _show(value: object) -> str:
    """Render a result the way the spec writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"%s"' % value
    return str(value)


def _apply_operation(operation: types.Operation, qualities: dict[str, QualityValue]) -> QualityValue:
    """Apply ``operation`` to ``qualities`` in place and return the subject's new value."""
    value = operation.evaluate(qualities.get(operation.quality), qualities=qualities)
    qualities[operation.quality] = value
    return value


def _final_value(item: str, qualities: dict[str, QualityValue]) -> QualityValue | bool:
    """Evaluate a result line's final item as an operation, a comparison, or an expression."""
    try:
        return _apply_operation(parsers.OperationParser().parse(item), qualities)
    except exceptions.OperationParseError:
        pass
    try:
        comparison = parsers.ComparisonParser().parse(item)
    except exceptions.ParsimoniousParseError:
        return _apply_operation(parsers.OperationParser().parse("_ = " + item), qualities)
    return comparison.evaluate(qualities.get(comparison.quality), qualities=qualities)


def _run_result(text: str) -> None:
    """Run a ``setup ; final → expected`` line, raising AssertionError on a wrong result."""
    left, _, right = text.partition(" → ")
    expected = _parse_literal(right.strip())
    *setup, final = left.split(" ; ")
    qualities: dict[str, QualityValue] = {}
    for step in setup:
        _apply_operation(parsers.OperationParser().parse(step.strip()), qualities)
    got = _final_value(final.strip(), qualities)
    if type(got) is not type(expected) or got != expected:
        raise AssertionError("%s: expected %s, got %s" % (text, _show(expected), _show(got)))


def run_example(example: SpecExample) -> None:
    """Run ``example`` against the real implementation, raising AssertionError on mismatch."""
    try:
        if example.kind == "result":
            _run_result(example.text)
        elif example.kind == "operation":
            parsers.OperationParser().parse(example.text).evaluate(None)
        else:
            comparison = parsers.ComparisonParser().parse(example.text)
            comparison.evaluate(None, qualities={})
    except AssertionError:
        raise
    except Exception as error:
        raise AssertionError(
            "%s (§%s, line %d): %s: %s" % (example.text, example.section, example.line, type(error).__name__, error)
        ) from error
