# Contract: Spec examples run as tests (FR-020, US6, PD-16)

**Surface**: `tests/test_spec_examples.py` (new) reading `docs/RAVEL_LANGUAGE_SPEC.md` at test
time. The spec's example blocks become the test data; the spec text is the contract.

The extractor and runner live in `tests/spec_examples.py`, a non-test helper module beside
`tests/helpers.py` (not collected by pytest, and outside the `--cov=ravel` gate):

```python
@dataclass(frozen=True)
class SpecExample:
    section: str  # "5", "7", "11.4", ...
    line: int  # 1-based line number in the markdown
    text: str  # the example as written (comment stripped)
    kind: Literal["result", "operation", "comparison"]


def extract_examples(markdown: str) -> list[SpecExample]: ...
def run_example(example: SpecExample) -> None:
    """Raise AssertionError naming the example on a wrong result or failed parse."""
```

`tests/test_spec_examples.py` parametrizes over `extract_examples(SPEC_PATH.read_text())`.
US6-AS2's acceptance test calls the same two functions on an edited copy of the text.

## Scope

Fenced code blocks (```` ``` ```` with any or no info string) whose nearest enclosing `## N.`
heading is §4, §5, §6, §7 or §9, or whose nearest `### 11.4` heading is §11.4. Blocks under other
headings are ignored (§10.1's PEG listing, §12's Cloak listing, appendices).

## Line classes

Each line in a scoped block is classified; the first matching class wins.

1. **Result line**: contains ` → ` (U+2192 with a space either side).
   - Left side: zero or more setup operations and one final item, separated by ` ; `
     (space-semicolon-space).
   - Right side: the expected result, a single literal: a number (`-5`, `1.0`), a quoted string
     (`"Foyer"`, `""`), or `true`/`false`. Anything after the literal separated by two or more
     spaces or opening with `(` is a comment (§5.1 already has `→ 2  (multiplication first)`).
   - Run: start from empty qualities, apply each setup operation in order, then:
     - final item parses as an **operation** → apply it; expected = the subject's new value;
     - else parses as a **comparison** → expected = its truth value;
     - else parses as an **expression** (via an operation `_ = <expr>` wrapper) → expected = its
       value.
   - Equality is value *and* type (`1` ≠ `1.0`), except that a result literal `true`/`false` is
     compared to `bool`.
2. **Operation item**: a YAML list item (`- …` or `- effect: …`) inside a block whose last
   enclosing YAML key is `given:` or `effect:`. It must parse via `OperationParser` and evaluate
   against empty qualities without raising.
3. **Comparison item**: a YAML list item under a `when:` key, or a `{…}` prefix at the start of a
   list item. It must parse via `ComparisonParser` and evaluate against empty qualities without
   raising.

**Raising path (RT-11).** `run_example` evaluates comparisons with
`Comparison.evaluate(qualities.get(subject), qualities=qualities)`, never `check`/`__call__`:
those return `False` on an evaluation error (RT-10), which would let a broken comparison example
pass silently. Result lines that end in a comparison use the same raising call.
4. Everything else (prose, text directives, keys, comments, blank lines) is ignored. A trailing
   ` # comment` on a YAML line is stripped before parsing.

A bare list item with no enclosing `given:`/`effect:`/`when:` key is ignored, because it can't be
told apart from a text directive. So the v0.2 spec nests §6.2's comparison list under `when:` (a
one-line edit) instead of the extractor guessing from the section number.

## Test ids and the guard

- Each example is one parametrized case, id `§<section>:<line number>: <example text>`, so a
  failure names the example and where it is.
- `test_extraction_counts` pins the number of examples found per section (a dict literal in the
  test module). A broken extractor finding nothing fails it; so does adding or deleting a spec
  example without updating the pin, which is the intended friction.

## Examples

Spec text (§5.1, v0.2):

```
10 - 4 - 2        → 4
8 / 4 / 2         → 1.0
2 + 3 * 4         → 14
X = 10 ; X += value * 2 → 30
X = 5 ; X -= 10 min 0   → 0
Name = "Wearing Cloak" ; Name == "Wearing Cloak" → true
```

→ six passing cases. Editing the first to `→ 8` fails
`§5:<line>: 10 - 4 - 2 → 8` with `expected 8, got 4` (US6-AS2).

Spec text (§7.3):

```yaml
effect:
  - Health -= 10 min 0       # Cannot go below 0
```

→ one operation case, `Health -= 10 min 0`, which must parse and evaluate on empty qualities
(result 0, not asserted).
