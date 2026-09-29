# Data Model: Ravel Spec Compliance (002)

Only entities this feature adds or changes are listed. Everything else in
`specs/001-reentrant-vm/data-model.md` (engine state, outputs, save file) is unchanged.

## Expression tree (`ravel.types`, strict mypy)

An expression compiles to a *term*: a literal, a reference, or an `Expression` node.

```python
type Term = int | float | str | QualityRef | Value | Expression
```

| Type | Fields | Evaluates to | Change |
|---|---|---|---|
| `int` / `float` | — | itself | literals may now be negative (PD-02) |
| `str` | — | itself | may now be `""` (PD-03) |
| `QualityRef` | `name: str` | `qualities.get(name)`, or `0` if unset | **new** (PD-04) |
| `Value` (singleton `VALUE`) | — | the context's `qvalue` | was a bare class; now an instance with `evaluate` (PD-06) |
| `Expression` | `term1: Term`, `operator: str`, `term2: Term` | `operator(term1, term2)` | unchanged shape; trees are now **left-nested** (PD-01) |

**Validation rules**

- `QualityRef.name` is non-empty. Bracketed names drop their brackets; identifiers match
  `[^\W\d]\w*` and aren't `value`, `min` or `max` (R4).
- `Expression.operator` is one of `+ - * / // %`. `* / // %` bind tighter than `+ -`; both tiers
  associate left.
- `Value` exists only inside an operation's or comparison's expression (grammar-enforced; PD-07).

**Evaluation context** (keyword-only, passed down the whole tree):

```python
class QualityLookup(Protocol):
    def get(self, name: str, /) -> QualityValue | None: ...


def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue: ...
```

`engine.state.Qualities` and `dict[str, QualityValue]` both satisfy `QualityLookup`.
`ravel.utils.data.evaluate_term(term, **context)` stays the dispatcher for "call `evaluate` if it
has one, else it's a literal".

## `Constraint` (`ravel.types`)

| Field | Type | Rule |
|---|---|---|
| `kind` | `Literal["min", "max"]` | from the grammar |
| `value` | `int \| float` | a signed number literal (PD-02); never an expression |

`Constraint.apply(result) -> QualityValue`: `min` → `max(result, value)`; `max` →
`min(result, value)`. A `str` result raises `ravel.exceptions.ConstraintError` (PD-08). The
clamped result takes the bound's kind when the bound wins.

## `Operation` (`ravel.types`)

| Field | Type | Change |
|---|---|---|
| `quality` | `str` | subject; unchanged (quoted, bracketed or `[^\s]+`) |
| `operator` | `str` | unchanged (`= += -= *= /= //= %=`) |
| `expression` | `Term` | may now hold `QualityRef` and a working `VALUE` |
| `constraint` | `Constraint \| None` | now **applied** (PD-08) |

`Operation.evaluate(initial_value: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES) -> QualityValue`:

1. `current = 0 if initial_value is None else initial_value`
2. `rhs = evaluate_term(expression, qualities=qualities, qvalue=current)`
3. `result = operator(current, rhs)`
4. `return constraint.apply(result) if constraint else result`

`Operation.get_expression` (a dead stub returning `None`) is deleted.

## `Comparison` / `Predicate` / `Text` (`ravel.types`)

`Comparison.evaluate(qvalue, *, qualities=EMPTY_QUALITIES)`, `Comparison.check(qualities)`,
`Predicate.check(qualities)` and `Text.check(qualities)` all forward `qualities` so the expression
can read references. `EMPTY_QUALITIES` is an immutable empty mapping (a `MappingProxyType({})`),
so a caller that tests a comparison with no context (existing unit tests, the `predicate(0)`
fallback in `queries.py`) keeps working.

## Errors

| Error | Module | Base | Raised when |
|---|---|---|---|
| `EvaluationError` | `ravel.exceptions` | `ValueError` | base for run-time expression failures this feature defines |
| `ConstraintError` | `ravel.exceptions` | `EvaluationError` | a constraint meets a non-numeric result |
| `InvalidOperationError` | `ravel.engine.errors` | `EngineError` | `_apply_operation` caught an `EvaluationError`, `ArithmeticError` or `TypeError` from an operation (chained as `__cause__`; RT-1) |
| `OperationParseError` | `ravel.exceptions` | `ParseError` | *existing*; now also for a constraint on a string literal (`X = "a" max 3`) |

`ravel.exceptions` imports `Source` from `syml.basetypes` instead of `ravel.types` so `types.py`
can import `ConstraintError` without a cycle.

**Condition failures are false (RT-2, RT-10).** `Comparison.check`/`Comparison.__call__` return
`False`, with no log call, when evaluation raises `TypeError`, `ArithmeticError` or
`EvaluationError`: a condition that cannot be evaluated is false (defined behavior).
`Comparison.evaluate` still raises. So a failing `when:` predicate is a
non-match (both `query_predicates` branches) and a failing `{…}` prefix hides its line; nothing is
raised to the engine. Operations, by contrast, raise `InvalidOperationError`.

## Concept registry (`ravel.compiler.concepts`)

`is_registered(name: str) -> bool` is new: `name in _HANDLERS`. Used by `compile_rulebook`'s
concept detection (PD-09). The registry's contents don't change: `Situation` is the only built-in.

## Loaders and story sources

| Type | Module | Layer | Fields | Behavior |
|---|---|---|---|---|
| `Environment` | `ravel.environments` | compile | `loader` (**required**, has callable `load`), `location_separator="::"`, `initializing_name="begin"`, `cache` | `Environment()` → `TypeError` (PD-12); no import of `ravel.loaders` |
| `BaseLoader` | `ravel.loaders` | compile | — | unchanged |
| `FileSystemLoader` | `ravel.loaders` | adapter | `base_path`, `extension` | unchanged |
| `MemoryLoader` | `ravel.loaders` | compile (no I/O) | `sources: Mapping[str, str]` (copied to a `dict` at construction) | **new**; missing name → `RulebookNotFound(name)`; always up to date |
| `FileSystemStorySource` | `ravel.adapters.story_source` | adapter | `directory` | unchanged |
| `MemoryStorySource` | `ravel.adapters.story_source` | adapter | `sources`, `entry="begin"` | **new**; `load()` compiles a fresh `Story` via `MemoryLoader` |

## State transitions

None new. Constraint clamping and quality references change *values* inside the existing
`_apply_operation` step; the engine's `WAITING`/`HALTED` transitions and the save file are
unchanged (save format stays v1; PD-14).

## Include loading (unchanged code, now pinned)

`Environment.load_rulebook(name)`: a FIFO queue seeded with `name`; pop, skip if already loaded,
compile, enqueue its unseen includes. Each rulebook compiles once; cycles terminate because a
loaded name is never compiled again. Merge: concepts' `rules` concatenate then sort; `locations`
merge (names are namespaced, so no collisions); `metadata` merges with later-loaded keys winning;
`givens` concatenate in load order, so later-loaded values for the same quality win at `start`.
