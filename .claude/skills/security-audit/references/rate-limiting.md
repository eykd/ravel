# Resource Limits & Denial-of-Service Prevention

## Purpose

A compiler/VM library has no network layer to rate-limit, but it has the
equivalent problem: a caller can hand the loader/compiler an arbitrarily
large or adversarially-shaped `.ravel` rulebook. Without bounds, a single
load-and-compile can exhaust CPU (catastrophic regex backtracking in a
Parsimonious grammar), memory (huge input held in full, or a runaway
`include:` chain), or the stack (deep recursion in the compiler or VM),
turning one load into a denial-of-service for the calling process.

## When to Apply Resource Limits

Apply a limit whenever an untrusted rulebook reaches the loader/compiler:

- Story files loaded from a repo a CI job doesn't fully control
- Any `.ravel` rulebook accepted over a network boundary (uploaded, fetched,
  or received from another service)
- Batch compilation of many rulebooks from an external source

Trusted, developer-authored fixtures in this repo's own test suite (e.g.
`examples/cloak/`) do not need these limits applied at the call site — they
need coverage from the *attacker's* perspective in the test suite instead
(see Testing below).

## Resource Limit Categories

| Resource            | Attack shape                                      | Mitigation                                          |
| -------------------- | --------------------------------------------------- | ------------------------------------------------------ |
| Input size            | Multi-gigabyte `.ravel` file                        | Caller-enforced size cap before calling `Environment.load()` |
| Include-chain depth   | A rulebook whose `include:` graph cycles or fans out enormously | Cap on the number of rulebooks a single `load()` will merge |
| Recursion depth       | Thousands of nested predicate/effect structures      | Depth counter in the compiler's recursive-descent handlers |
| Regex backtracking    | Pathological strings against grammar terminals in `grammars.py` | Avoid nested-quantifier patterns; fuzz them          |
| VM action-queue growth | A rulebook whose directives push unboundedly many actions | Cap on queued actions per `push`/`pop` cycle in `vm/machines.py` |

## Recursion Depth Limiting

The compiler (`compiler/rulebooks.py`, `compiler/situations.py`,
`compiler/directives.py`) walks nested directive/effect structures
recursively; its cost scales with nesting depth supplied by the input
itself — not by anything the library controls internally.

```python
# Illustrative pattern: bound recursive compiler operations by an explicit
# depth limit rather than relying on Python's default recursion limit, which
# raises an unstructured RecursionError deep inside compiler code rather
# than a typed ParseError at a clean boundary.

MAX_NESTING_DEPTH = 500


def compile_directive(environment, concept, parent_rule, raw_directive, depth=0):
    if depth > MAX_NESTING_DEPTH:
        raise exceptions.ParseError(f"exceeded max nesting depth ({MAX_NESTING_DEPTH})")
    # ... existing directive-compiling logic, threading depth + 1 through
    # any recursive call ...
```

Prefer converting an unbounded recursive walk to an explicit loop with a
depth counter over raising Python's recursion limit — raising the limit only
moves the crash point and makes a stack-exhaustion segfault more likely
instead of a clean, typed exception.

## Input Size and Include-Chain Limiting (Caller Responsibility)

Neither `Environment.load()` nor `FileSystemLoader.get_source` enforces a
size limit or an include-chain bound themselves — that decision belongs to
the caller that knows its trust boundary. `Environment.load_rulebook` uses a
`deque` BFS over `include:` names, caching each compiled rulebook, so a
cyclic or enormous include graph is at least visited once per name rather
than infinitely — but nothing caps how many *distinct* names it will chase.

```python
# Caller-side pattern for an untrusted-input boundary (e.g. a web service
# that accepts rulebook uploads) — not something ravel itself imposes.
MAX_RULEBOOK_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_INCLUDED_RULEBOOKS = 200


def load_untrusted_story(environment, name: str) -> dict:
    rulebook = environment.load_rulebook(name)
    if len(environment.cache) > MAX_INCLUDED_RULEBOOKS:
        raise ValueError(f"rulebook pulled in more than {MAX_INCLUDED_RULEBOOKS} includes")
    return rulebook
```

## Regex / Grammar Backtracking (ReDoS)

Parsimonious PEG grammars (`grammars.py`) are still susceptible to
backtracking blowup if a rule's regex terminal has nested quantifiers or
ambiguous alternation against long adversarial strings (e.g. `"   " * 100000`
against an indent-matching rule, or a long run of near-matching-but-not text
against `plain_text_grammar`).

```python
# Vulnerable shape: nested quantifiers over attacker-controlled length
BAD_PATTERN = r"(\s*)+:"

# Prefer a single bounded quantifier per character class
GOOD_PATTERN = r"\s*:"
```

Stress-test any regex terminal with long, near-matching (but not fully
matching) strings — that is where catastrophic backtracking shows up, not
in strings that match cleanly or fail immediately.

## Testing Resource Limits

### Unit Tests

```python
import pytest

from ravel import exceptions


def test_it_should_reject_input_beyond_max_nesting_depth():
    """A pathologically deep directive structure should raise ParseError, not RecursionError."""
    deeply_nested = {"effect": {"foo": "bar"}}
    for _ in range(2000):
        deeply_nested = {"effect": deeply_nested}
    with pytest.raises(exceptions.ParseError):
        compile_directive(environment, concept, parent_rule, deeply_nested)


def test_it_should_parse_within_bounded_time_for_long_lines():
    """A very long single line must not trigger catastrophic backtracking."""
    import time

    pathological = "Foo!" + ("a" * 200_000)
    start = time.monotonic()
    parsers.PlainTextParser().parse(pathological)
    assert time.monotonic() - start < 1.0
```

### Property-Based Tests

`hypothesis` is not currently a dev dependency of this repo — add it
(`uv add --dev hypothesis`) before writing property-based tests like this
one:

```python
from hypothesis import given, settings, strategies as st


@given(st.integers(min_value=1, max_value=5000))
@settings(deadline=None)
def test_it_should_never_hang_on_arbitrary_nesting_depth(depth):
    """Compiling must terminate (raise or succeed) regardless of nesting depth."""
    directive = {"effect": {"foo": "bar"}}
    for _ in range(depth):
        directive = {"effect": directive}
    try:
        compile_directive(environment, concept, parent_rule, directive)
    except Exception:  # any typed failure is acceptable here
        pass
```

## Security Best Practices

### 1. Fail Fast, Fail Typed

Every resource-limit violation should raise a typed `ravel.exceptions`
subclass, never let Python's own limits (`RecursionError`, `MemoryError`)
escape uncaught from inside the grammar or compiler.

### 2. Separate Library Limits From Caller Policy

The library enforces limits that protect its own internals (recursion
depth, backtracking-safe regexes). Size and include-chain limits that
depend on the caller's trust model (how big is "too big" for *this*
deployment) belong at the call site, documented so callers know they must
add them.

### 3. Log Enough to Diagnose, Not Enough to Leak

If a resource-limit rejection is logged, include the limit and the
input's size/depth, not the full untrusted content.

### 4. Test From the Attacker's Perspective

Fuzz and property-test the loader/compiler entry points with adversarial
shapes (deep nesting, pathological regex inputs, huge single lines, wide
include graphs) as a standing part of the test suite, not a one-off manual
check.

## Common Mistakes

### Relying on Python's Default Recursion Limit

```python
# Crashes with an unstructured RecursionError deep in compiler code instead
# of raising a typed exception at a clean boundary.
def compile_nested(directive):
    return compile_nested(directive["effect"]) if "effect" in directive else directive
```

### Assuming Small Test Fixtures Represent Worst-Case Input

Correctness tests use small, readable fixtures (`examples/cloak/`,
`examples/simple/`). Resource-limit tests need their own
adversarially-shaped fixtures (deep nesting, long lines, near-matching regex
input, wide include graphs) — the two suites test different properties.

### Explicit Depth Counter With a Typed Error

```python
def compile_directive(environment, concept, parent_rule, raw_directive, depth=0):
    if depth > MAX_NESTING_DEPTH:
        raise exceptions.ParseError("exceeded max nesting depth")
    # ... recurse with depth + 1 ...
```

## Related Skills

- **security-audit**: Untrusted-input handling, ReDoS, file handling
- **quality-review**: Test quality for adversarial/property-based cases
