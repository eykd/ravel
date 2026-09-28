---
name: acceptance-tests
description: >
  Writing Gherkin acceptance specs and binding them with pytest-bdd.
  Use when creating new specs in specs/acceptance-specs/, binding a scenario's
  steps into tests/acceptance/, or troubleshooting the acceptance pipeline.
triggers:
  - write spec
  - write acceptance test
  - bind acceptance test
  - Gherkin spec
  - pytest-bdd
  - acceptance stub
  - spec writing
---

# Acceptance Tests Skill

**Status note (ported from syml):** this skill describes a Gherkin/pytest-bdd
acceptance pipeline (`specs/acceptance-specs/`, `tests/acceptance/`, a
`just acceptance` recipe) that does not exist yet in this repo. Ravel has no
`specs/` directory, no `tests/acceptance/` directory, no `pytest-bdd`
dev dependency, and no `justfile`. Treat the sections below as a design for
*if/when* an acceptance layer is added on top of ravel's existing unit suite
(`tests/*.py`, run via `./runtests.sh`) — not as a pipeline you can invoke
today. The domain-language discipline (writing specs in terms of `.ravel`
rulebooks, situations, and qualities rather than implementation internals) is
useful guidance regardless, and is kept in ravel's own vocabulary below.

## Decision Tree

```
What do you need?
│
├─ Write a new spec file (once the pipeline exists)
│  → Section: Writing Gherkin Specs (below)
│  → Reference: references/gwt-writing-guide.md
│
├─ Bind a scenario's steps into a real test (once pytest-bdd is a dependency)
│  → Section: Binding Steps (below)
│  → Reference: references/binding-patterns.md
│
├─ Understand the TDD cycle around ravel's existing unit tests
│  → Skill: pytest-unit-testing (inner Red-Green-Refactor loop)
│  → Skill: test-driven-development (generic TDD discipline)
```

## Writing Gherkin Specs

If an acceptance layer is added, specs would live in
`specs/acceptance-specs/` as Gherkin `.feature` files, with
`bdd_features_base_dir` set in `pyproject.toml` so a binding's
`scenarios("US<NN>-<slug>.feature")` call resolves relative to that
directory — pass just the filename, not the full path.

### File Naming

```
specs/acceptance-specs/US<NN>-<kebab-case-title>.feature
```

One file per user story. The `US<NN>` prefix should match the story number
used in beads (`ravel-<id>`).

### Format

```gherkin
Feature: Short name for the user story
  A one- or two-sentence narrative: who wants this and why.

  Scenario: Description of the scenario
    Given some precondition
    When an action occurs
    Then an observable outcome

  Scenario Outline: Description with variation
    Given a rulebook containing "<input>"
    When it is compiled
    Then the result is "<expected>"

    Examples:
      | input             | expected          |
      | look-in-dark: text | look-in-dark: text |
```

- `Feature:` line plus narrative, then one or more `Scenario:` blocks
- Steps use `Given`/`When`/`Then`, with `And`/`But` to continue a step's kind
- `Scenario Outline:` plus an `Examples:` table parameterizes a scenario over several rows
- Write natural Gherkin sentences, no trailing periods required
- Multiple scenarios per feature file are allowed and encouraged: cover the happy path, edge cases, and error cases as separate scenarios in the same file

### Domain Language Discipline

Specs describe **what a `.ravel` rulebook contains and what compiling/running
it produces**, never how the compiler or VM is implemented internally.

**Good** — domain language:

```gherkin
Scenario: A situation's rules are scored by predicate specificity
  Given a rulebook with two matching situations of different specificity
  When the situations are queried against the current qualities
  Then the more specific situation is chosen

Scenario: An unregistered directive fails to compile
  Given a rulebook whose situation uses an unknown directive
  When it is compiled
  Then compilation fails with an out-of-context error naming the directive
```

**Bad** — implementation leakage:

```gherkin
Scenario: The compiler dispatches to the concept handler
  Given a concept handler is registered via @concepts.handler
  When compile_baggage is called
  Then a types.Rule is appended to the ruleset
```

Rules:

- No code identifiers (class names, function names, module paths)
- No compiler/VM internals (`compile_baggage`, `@concepts.handler`,
  `NodeVisitor`, `VirtualMachine`, `do_push`/`do_pop`)
- No Python exception class names in step text — describe the failure in
  domain terms ("compilation fails with an out-of-context error naming the
  directive"), and let the binding assert on the concrete exception type
- Talk about the rulebook (situations, qualities, predicates, choices,
  effects) and what compiling/querying/running it produces or raises —
  never about how the grammar or VM gets there

See `references/gwt-writing-guide.md` for detailed examples and a review checklist.

## Binding Steps

### Architecture

```
specs/acceptance-specs/US<NN>-<slug>.feature  →  scenarios()  →  tests/acceptance/test_us<nn>_<slug>.py
```

pytest-bdd binds directly: a binding module calls
`scenarios("US<NN>-<slug>.feature")` and defines `@given`/`@when`/`@then`
step functions matching the feature's step text. There is no generated-stub
file to edit — you write the binding module yourself.

### Binding Module Shape

```python
"""Bindings for specs/acceptance-specs/US01-situation-scoring.feature."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ravel import compiler, queries

pytestmark = pytest.mark.acceptance

scenarios("US01-situation-scoring.feature")


@given(parsers.parse('a rulebook containing "{text}"'))
def given_rulebook(context, text):
    context["text"] = text


@when("the situations are queried against the current qualities")
def when_queried(context):
    context["result"] = queries.query(context["qualities"], context["predicates"])


@then(parsers.parse("the more specific situation is chosen"))
def then_more_specific(context):
    assert context["result"]
```

Key points:

- `pytestmark = pytest.mark.acceptance` — a marker registered in
  `pyproject.toml` so the acceptance suite can be selected/deselected
- `scenarios("US<NN>-<slug>.feature")` — binds every scenario in that
  feature file to this module; the path resolves against
  `bdd_features_base_dir`
- A `context` fixture carries state from `Given` to `When` to `Then` within
  one scenario
- `parsers.parse(...)` extracts `{placeholders}` from step text into
  function arguments — see `references/binding-patterns.md` for
  `parsers.re`, `parsers.cfparse`, and `target_fixture`

See `references/binding-patterns.md` for parser choices, `target_fixture`,
shared steps, Scenario Outline examples, tables, and error assertions.

## References

- `references/gwt-writing-guide.md` — Detailed Gherkin writing craft, good/bad examples, review checklist
- `references/binding-patterns.md` — Code templates for pytest-bdd step bindings
- **pytest-unit-testing** skill — pytest conventions, TDD micro loop, coverage policy
- **test-driven-development** skill — generic TDD discipline (Test List, Red-Green-Refactor)
