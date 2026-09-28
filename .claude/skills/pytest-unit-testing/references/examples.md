# Example Tests

These examples follow the real `ravel` API and the conventions described in
`SKILL.md`: class-based grouping, `test_it_should_...` naming, unannotated
test bodies (mypy does not check `tests/`), `pytest.mark.parametrize`, and
`pytest.raises(..., match=...)`.

## A Simple Direct Assertion

```python
from ravel import parsers, types


class TestPlainTextParser:
    def test_it_should_parse_plain_text_without_features(self):
        result = parsers.PlainTextParser().parse("Nothing to see here.")
        assert result == types.Text("Nothing to see here.")
```

## Parametrized Cases

```python
import pytest

from ravel import parsers, types


class TestPlainTextParserParametrized:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Nothing to see here.", types.Text("Nothing to see here.")),
            ("Sticky web. <>", types.Text("Sticky web. ", sticky=True)),
        ],
    )
    def test_it_should_parse_various_shapes(self, text, expected):
        assert parsers.PlainTextParser().parse(text) == expected
```

Each row becomes its own test id in `-v` output
(`test_it_should_parse_various_shapes[Nothing to see here.-expected0]`,
etc.), so a failure names the exact input that broke.

## Asserting a Raised Exception with `match=`

```python
import pytest

from ravel import exceptions

from .helpers import source


class TestRaiseParseError:
    def test_it_should_raise_a_comparison_parse_error_for_known_source(self):
        with pytest.raises(exceptions.ComparisonParseError):
            exceptions.raise_parse_error(source("foo"), exceptions.ComparisonParseError)
```

`match` is searched against `str(exception)` — pin the assertion to the
specific message content the failing path raises, not just "some
`ParseError` subclass was raised somewhere."

## Testing Grammar/Parser Behavior End to End

For parser and compiler behavior, prefer driving the real grammar over
hand-building the intermediate `types.py` value objects. `compile_rulebook`
(in `ravel.compiler.rulebooks`) takes an `Environment` and a parsed rulebook
mapping and returns the compiled rules dict — see `tests/test_compiler_rulebooks.py`
for the real fixture setup and `tests/test_compiler_*.py` for the individual
directive/predicate/effect compilers, rather than reconstructing the
`Environment` wiring from scratch in a new reference example here.

## Testing the VM

Drive the VM through its public push/pop queue and assert on emitted
`vm/events.py` events (via `blinker` signals), following
`tests/test_vm_machine.py` and `tests/test_vm_states.py` — never by poking
at `VirtualMachine` internals directly.

## Loading a Real Example

`tests/conftest.py` loads `examples/cloak/` as a fixture — reach for it (or
`examples/taxi/`, `examples/simple/`) instead of hand-rolling rulebook dicts
whenever a test needs realistic, multi-rule `.ravel` content.
