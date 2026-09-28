---
name: pytest-unit-testing
description: 'Use when: (1) writing new unit tests for ravel, (2) reviewing existing tests, (3) implementing TDD workflows, (4) creating fixtures/parametrized cases, (5) debugging test failures, (6) questions about test design. Covers pytest, mypy, and ruff conventions in this repo.'
---

# Python Unit Testing with pytest & TDD

This skill is the **pytest layer** over `/test-driven-development` — see that
skill for the TDD discipline itself (the Test List, Red-Green-Refactor, the
greening strategies, and the generic test references). This skill covers the
pytest/mypy/ruff conventions specific to `ravel` and this project's **100%
branch-coverage mandate**.

## Core Decision: What Are You Testing?

| Scenario                              | Approach                                  |
| -------------------------------------- | ------------------------------------------ |
| A pure function/parser (`parsers.py`)  | Test directly, no mocks                    |
| A compiled value type (`types.py`)     | Fresh instance per test, no shared state   |
| A grammar/parser behavior              | Drive it through the relevant `parsers.py` grammar wrapper, not raw parsimonious internals |
| The VM (`vm/machines.py`, `vm/states.py`) | Drive it through `push`/`do_push` and assert on emitted `vm/events.py` events via blinker signals, not by reaching into VM internals |
| A genuinely unreachable branch         | Delete the stub, or test it directly — not a pragma (see below) |

Most of ravel's core (grammars, compiler, queries) has little I/O and few
external dependencies to mock — most tests are plain input → output
assertions against a parser or compiler function. The VM and loader layers do
touch the filesystem (via `Environment`/`Loader`) and blinker signals; use the
`examples/cloak` fixture (loaded in `tests/conftest.py`) for realistic
end-to-end cases rather than hand-rolling rulebook dicts everywhere.

## File and Test Naming

- One test module per source module: `tests/test_<module>.py` mirrors
  `src/ravel/<module>.py` (`tests/test_parsers.py` ↔ `src/ravel/parsers.py`,
  `tests/test_vm_machine.py` ↔ `src/ravel/vm/machines.py`).
- Group related tests in a class named after the unit under test:
  `class TestIntroTextParser:`, `class TestPlainTextParser:`. This is the
  established pattern in `tests/test_parsers.py` — follow it for new test
  modules rather than inventing a flat function-per-test style.
- Test method names read as a sentence: `test_it_should_parse_intro_text_with_a_suffix_and_a_tail`,
  `test_it_should_raise_on_a_bad_dedent`. Start with `test_it_should_...`
  (or `test_it_...` for a negative/failure case) and describe the observable
  behavior, not the implementation path.

## Type Annotations in Tests Are Optional

mypy's `files` setting in `pyproject.toml` is `["src", "tools"]` — `tests/`
is **not** type-checked, and mypy is not run in strict mode even on `src/`
(most function bodies are unannotated and mypy skips them unless
`check_untyped_defs` is set). Existing tests follow this: fixtures and test
methods are usually left unannotated, matching `tests/test_parsers.py`:

```python
import pytest

from ravel import parsers, types


class TestPlainTextParser:
    @pytest.fixture
    def parser(self):
        return parsers.PlainTextParser()

    def test_it_should_parse_plain_text_without_features(self, parser):
        result = parser.parse("Nothing to see here. Move along.")
        assert result == types.Text("Nothing to see here. Move along.")
```

`uv run mypy` must still pass with zero errors before committing — it just
won't be checking `tests/`.

## `pytest.mark.parametrize` for Tables

Prefer `parametrize` over near-duplicate test methods whenever the only
difference between cases is the input/expected pair:

```python
import pytest

from ravel import parsers, types


class TestPlainTextParser:
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

Each parametrized case shows up as its own entry in `-v`/`-vv` output, so
failures point straight at the failing input.

## `pytest.raises` with `match=`

Always assert on the exception message (or a stable substring of it) with
`match=`, not just the exception type — a bare `pytest.raises(SomeError)`
passes even if the wrong branch raised it:

```python
import pytest

from ravel.exceptions import OutOfContextNodeError


class TestOutOfContextError:
    def test_it_should_raise_on_an_unregistered_directive(self):
        with pytest.raises(OutOfContextNodeError, match="not registered"):
            ...  # drive the compiler/VM path that raises it
```

`match` takes a regex searched against `str(exception)`, so escape any
regex metacharacters that appear in the literal text you're matching.

## Test Isolation

There is no random-order test runner configured (`pytest-random-order` is
not a dev dependency here). Still write isolated tests:

- No shared mutable module- or class-level state between tests
- No test that depends on another test having run first
- Fixtures are function-scoped by default (`@pytest.fixture` with no
  `scope=`) — keep it that way unless you have a specific, documented reason
  for a broader scope

## Coverage Policy: No Pragma-on-Unreachable-Branch

The coverage gate (`fail_under = 100` in `[tool.coverage.report]`, branch
coverage on via `--cov-branch`) is enforced by `./runtests.sh` and CI. Per
`CLAUDE.md`, there are no `# pragma: no cover` marks left in `src/` to
imitate.

Before reaching for a pragma, ask: can this branch actually be exercised by
a test? Almost always yes. If a branch is reachable by *some* real `.ravel`
source or Python call, write that test — don't skip it because writing the
test is inconvenient or because triggering an error path takes a slightly
awkward input.

If a branch is genuinely unreachable (e.g. an abstract method's default body
that every concrete subclass overrides, or a defensive `else` a grammar
makes unreachable), don't pragma it away — either delete the unreachable
stub, or write a direct test that exercises it, so the coverage gate stays
honest about what's actually exercised.

## Running a Single Test File

```sh
uv run pytest tests/test_parsers.py::TestPlainTextParser::test_it_should_parse_plain_text_without_features --no-cov
```

`--no-cov` matters here: a single-file or single-test run will always report
far under 100% (everything else in `src/` looks "uncovered" from that one
run's perspective) unless you suppress it. Coverage numbers are only
meaningful for a full `./runtests.sh` run.

For the fast iterate-until-green loop use `./runtests.sh`
(`--failed-first --exitfirst --cov=ravel --cov=tools --cov-branch`), then
`uv run ruff check --fix`, `uv run ruff format`, and `uv run mypy` before
committing.

## TDD Red/Green/Refactor Cycle

This repo's outer loop (ralph / `/sp:*`) treats a RED commit as a distinct,
inspectable step:

1. **Red**: write a failing test first. If it exercises a not-yet-existing
   name, stub the implementation with `raise NotImplementedError` and a full
   type signature, so mypy and test collection both pass while the test
   itself still fails on the assertion:

   ```python
   def parse_something(text: str) -> dict[str, str]:
       """Parse a not-yet-implemented shape."""
       raise NotImplementedError
   ```

2. Confirm the test actually fails (`uv run pytest <path> --no-cov`), then
   record the RED commit: `.venv/bin/python -m tools.commit_red <task-id>`.
   This is a ralph-worker/`/sp:*` convention — it marks that a real failing
   test exists before implementation starts, so the outer loop can prove the
   test wasn't vacuous.
3. **Green**: write the minimum implementation to pass. Run the full
   `./runtests.sh` (so coverage is meaningful) before moving on.
4. **Refactor**: with tests green, clean up duplication or naming under the
   safety net, re-running the suite after each change.

See `/test-driven-development` for the underlying discipline (Kent Beck's
test desiderata, the Test List, when to fake it vs. obvious implementation).

## ruff Conventions for Tests

Ravel's `[tool.ruff.lint] select` is `["E", "F", "W", "B", "C4", "SIM", "I",
"UP"]` — a smaller set than a "batteries included" config. Notably, `S`
(bandit), `D` (pydocstyle), `INP` (implicit namespace packages), and `ARG`
(unused arguments) are **not** selected, so there is no need for
per-file-ignores exempting `tests/**/*.py` from bandit's bare-`assert` rule
or a docstring requirement — those rules simply aren't enabled. Everything
in the enabled set (`E`, `F`, `W`, `B`, `C4`, `SIM`, `I`, `UP`) still applies
to test files. Run `uv run ruff check --fix` and `uv run ruff format` before
committing; `./runtests.sh` does not run ruff itself, so run it separately
(or via `uv run pre-commit run --all-files`).

## References

- `references/examples.md` — Concrete, verified test examples against the
  real `ravel` API (`parsers`, `types`, `OutOfContextNodeError`, the VM)
- **acceptance-tests** skill — Gherkin/pytest-bdd layer above this one
- **test-driven-development** skill — generic TDD discipline (Test List,
  Red-Green-Refactor, greening strategies)
