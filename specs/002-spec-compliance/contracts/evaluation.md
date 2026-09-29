# Contract: Evaluation, `value` and constraints (FR-004 – FR-008)

**Surface**: `ravel.types` (`QualityRef`, `Value`/`VALUE`, `Expression`, `Constraint`,
`Operation`, `Comparison`, `Predicate`, `Text`), `ravel.queries.query_predicates`,
`ravel.engine.engine._apply_operation`, new errors in `ravel.exceptions` and
`ravel.engine.errors`. `ravel.types`, `ravel.queries` and `ravel.engine.*` are strict mypy
modules: every new or changed signature is fully annotated.

## Signatures

```python
# ravel/types.py
class QualityLookup(Protocol):
    def get(self, name: str, /) -> QualityValue | None: ...


EMPTY_QUALITIES: Final[Mapping[str, QualityValue]]  # MappingProxyType({})


@attr.s(frozen=True, slots=True)
class QualityRef:
    name: str

    def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue:
        """The named quality's value, or 0 if it's unset."""


@attr.s(frozen=True, slots=True)
class Value:
    def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue:
        """The subject's current value (``qvalue``)."""


VALUE: Final = Value()


class Expression:
    def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue: ...


class Constraint:
    kind: Literal["min", "max"]
    value: int | float

    def apply(self, result: QualityValue) -> QualityValue:
        """Clamp ``result``; raise ConstraintError if it's a str."""


class Operation:
    def evaluate(
        self, initial_value: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES
    ) -> QualityValue: ...


class Comparison:
    def evaluate(self, qvalue: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES) -> bool: ...
    def check(self, qualities: QualityLookup) -> bool: ...
    def __call__(self, qvalue: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES) -> bool: ...


# ravel/exceptions.py
class EvaluationError(ValueError): ...


class ConstraintError(EvaluationError): ...


# ravel/engine/errors.py
class InvalidOperationError(EngineError):
    """An operation's expression or constraint failed at run time."""
```

Every `qualities` defaults to `EMPTY_QUALITIES` and `qvalue` to `0`, so today's context-free
calls in `tests/test_types.py` (`exp.evaluate()`, `operation.evaluate(None)`) keep passing.
`Comparison.evaluate` treats a `None` subject as `0` (unchanged), then passes that as `qvalue`.
`queries.query_predicates(query, predicates)` builds `lookup = dict(query)` once and calls
`predicate(qvalue, qualities=lookup)` in both branches (set subject and the unset-subject
`predicate(0)` fallback). The fallback's `except TypeError` is unchanged.

`_apply_operation(qualities, operation)`:

```python
old = qualities.get(operation.quality)
try:
    new = operation.evaluate(old, qualities=qualities)
except EvaluationError as error:
    raise InvalidOperationError("%s: %s" % (operation_text, error)) from error
return qualities.set(operation.quality, new), QualityChanged(operation.quality, old, new)
```

## Examples: qualities + source → result

Each row runs `OperationParser().parse(src).evaluate(qualities.get(subject), qualities=qualities)`
(or `ComparisonParser().parse(src).check(qualities)`), which is what the engine does.

| Qualities before | Source | Result |
|---|---|---|
| — | `X = 10 - 4 - 2` | X = 4 |
| — | `X = 8 / 4 / 2` | X = 1.0 |
| — | `X = 2 + 3 * 4` | X = 14 |
| — | `X = 7 // 2 * 2` | X = 6 (one tier, left to right) |
| — | `X = 10 - 4 * 2` | X = 2 |
| — | `X = -5` | X = -5 |
| — | `X = -1.5` | X = -1.5 |
| — | `X = 10 - -4` | X = 14 |
| — | `X = ""` | X = `""` |
| Health = 7, Bonus = 3 | `X = [Health] + Bonus` | X = 10 |
| — | `X = Health + 1` | X = 1 (unset reads 0) |
| X = 10 | `X += value * 2` | X = 30 |
| Health = 50 | `Health -= value / 10` | Health = 45.0 |
| — | `X += value + 1` | X = 1 (unset subject: value = 0) |
| X = 5 | `X -= 10 min 0` | X = 0 |
| X = 5 | `X += 10 max 8` | X = 8 |
| X = 5 | `X += 1 max 8` | X = 6 |
| X = 5 | `X -= 10 min 0.0` | X = 0.0 (bound's kind) |
| X = 5 | `X = 20 max 8` | X = 8 (`=` clamps too) |
| — | `X -= 3 min -2` | X = -2 |
| Name = "Hi" | `X = Name max 3` | `ConstraintError` from `Operation.evaluate`; `InvalidOperationError` from the engine |
| Name = "Wearing Cloak" | comparison `Name == "Wearing Cloak"` | True |
| Name = "Wearing Cloak" | comparison `Name == [Wearing Cloak]` | False (reads the unset quality `Wearing Cloak`, i.e. 0) |
| Health = 7, Max = 10 | comparison `Health < [Max]` | True |
| Health = 7 | comparison `Health >= value` | True |
| — | comparison `Health > -1` | True (unset → 0) |

Through the engine:

- A `given:` holding `Gold = 50 max 20` → `start()` emits `QualityChanged("Gold", None, 20)`
  (US2-AS4).
- `when: X > Y` with X = 2 and Y = 1 → the rule matches in `query`; with Y = 3 it doesn't.
- `{Health < [Max]}Low.` shows `Low.` when Health = 7 and Max = 10.
