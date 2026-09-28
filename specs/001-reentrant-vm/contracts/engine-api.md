# Contract: Engine API (`ravel.engine`) — domain layer

Pure functions. No I/O, no callbacks, no module-level mutable state. Same inputs → same outputs
(FR-005, FR-008, FR-016). Types are defined in [data-model.md](../data-model.md).

```python
def start(story: Story) -> Step: ...
def choose(story: Story, state: GameState, location: LocationId) -> Step: ...
def present(story: Story, state: GameState) -> tuple[Output, ...]: ...
def validate_resumable(story: Story, state: GameState) -> None: ...  # raises InvalidStateError
```

## `start(story)`

1. `qualities = Qualities()`; apply `story.givens` in order, once each, emitting
   `QualityChanged(name, old, new)` (FR-014).
2. Run from the empty stack (query mode).

**Cloak** (US2-AS1):

```python
step = start(cloak)
step.outputs == (
    QualityChanged("Location", None, "Intro"),
    QualityChanged("Wearing Cloak", None, 1),
    ChoicesOffered((ChoiceOption("begin::intro", "Hurrying through the rainswept November night…"),)),
)
step.state.status is Status.WAITING
step.state.offered == ("begin::intro",)
step.state.stack == ()
step.state.qualities.as_dict() == {"Location": "Intro", "Wearing Cloak": 1}
```

(Other included rulebooks' givens, e.g. `bar-light`'s `Fumbled = 0, Bar = 0`, appear too, in
`Environment` BFS order; the assertion in tests is on the `begin` givens and "each applied once".)

## `choose(story, state, location)`

Preconditions, checked in this order; each raises and leaves `state` untouched (FR-015):

| Condition | Error |
|---|---|
| `state.status is HALTED` | `GameOverError("the game is over (outcome: 'won')")` |
| `state.status is not WAITING` | `NotWaitingError` |
| `location not in state.offered` | `NotOfferedError("'x' is not an offered choice; offered: [...]")` |

Then: if `state.stack` is non-empty, the top frame's ip is set to `GetChoice_index + 1`. Push
`Frame(location, 0)`, emit `SituationEntered(location)`, run.

**Run loop** (private; one call runs until YIELD or HALT):

| Situation | Action |
|---|---|
| stack empty | query `"Situation"`; 0 matches → halt `Outcome("", dead_end=True)`; else `offered` = matches (predicate count desc, then location ID desc), emit `ChoicesOffered`, status `WAITING`, return |
| top `ip >= len(directives)` | pop unconditionally, emit `SituationExited(location)` (FR-010) |
| `Text` | if `text.check(qualities)` and `text.text.strip()`: emit `TextShown(text.text, text.sticky)`; ip+1 |
| `Operation` | `new = op.evaluate(old, qualities=...)`; validate; emit `QualityChanged`; ip+1 |
| `BeginChoices` | gather the consecutive `Choice`s; ip ← index of `GetChoice`; emit `ChoicesOffered`; status `WAITING`; return |
| `End` | stack ← `()`, offered ← `()`, outcome ← `Outcome(end.outcome)`; emit `Halted(label, False)`; status `HALTED`; return |
| `Choice` / `GetChoice` reached directly, unknown directive type, ip out of range, unknown location | `InvalidStateError` (unreachable from engine-produced states; covered with hand-built states). Never `IndexError`/`KeyError` |

In-situation menus keep the block's source order; only query menus are sorted. "Location ID
descending" is Python `str` order (code points). Operations run through one private
`_apply_operation`: result must be in `QUALITY_TYPES = (int, float, str)`, not `bool`, finite if
float, and `-(2**63) <= v < 2**63` if int, else `InvalidQualityValueError`. `min`/`max` constraints
are **not** applied (inherited gap, documented in the VM spec).

**Gather example** (US2-AS3; fixture `mini`):

```yaml
fork:
  - when:
      - Location = "Fork"
  - You stand at a fork.
  - choice:
      - [Go left]You go left.
  - choice:
      - [Go right]You go right.
  - The road rejoins.
  - effect: Place = "Middle"
```

```python
s1 = choose(mini, s0, "begin::fork")
s1.outputs == (
    SituationEntered("begin::fork"),
    TextShown("You stand at a fork."),
    ChoicesOffered(
        (ChoiceOption("begin::fork::go-left", "Go left"), ChoiceOption("begin::fork::go-right", "Go right"))
    ),
)
s1.state.stack == (Frame("begin::fork", 4),)  # directives: 0 text, 1 BeginChoices, 2-3 Choice, 4 GetChoice
s1.state.qualities.get("Place") is None  # gather not run

s2 = choose(mini, s1.state, "begin::fork::go-left")
s2.outputs[:5] == (
    SituationEntered("begin::fork::go-left"),
    TextShown("You go left."),
    SituationExited("begin::fork::go-left"),
    TextShown("The road rejoins."),
    QualityChanged("Place", None, "Middle"),
)
# then SituationExited("begin::fork") and the next query menu (or halt)
```

**Errors** (`ravel.engine.errors`):

```python
class EngineError(Exception): ...


class NotOfferedError(EngineError): ...


class GameOverError(EngineError): ...


class NotWaitingError(EngineError): ...


# bool, NaN, ±inf, int outside signed 64-bit, str/name with a lone surrogate, non int/float/str
class InvalidQualityValueError(EngineError): ...


class InvalidStateError(EngineError): ...  # validate_resumable failures
```

A `ZeroDivisionError`/`TypeError` raised by an author's operation propagates unchanged (a story
bug, not an engine state); the CLI's `--debug` path handles it.

## `present(story, state)`

Re-presents a resting state without running anything (used after load, FR-023):
- `WAITING` → `(ChoicesOffered(...labels re-derived from story for state.offered...),)`
- `HALTED` → `(Halted(outcome.label, outcome.dead_end),)`

## `validate_resumable(story, state)`

Raises `InvalidStateError` naming the first violated invariant from the data-model table,
checking the **whole stack** bottom → top: unknown or non-`Situation` location; a bottom frame
that is not a `Situation` rule; status `RUNNING`;
halted with frames/offered; a non-top frame whose `ip - 1` is not a `GetChoice` or whose child
(the next frame up) is not one of that block's choices; top ip not on `GetChoice`; `offered` ≠
re-derived menu; outcome/status mismatch; a halted label not in `story.end_labels` (or a dead end
with a non-empty label); a quality value failing `Qualities` validation. Pure: re-derives the menu
with the same code path the run loop uses. `TypeError`/`ValueError`/`ZeroDivisionError` raised
while re-deriving a query menu over odd quality types are re-raised as `InvalidStateError`
(chained).

## Determinism and isolation

- Menu order pinned by `tests/engine/test_engine_query.py` (FR-011) and documented in VM spec §7.3.
- `choose(story, s, x)` called twice with the same arguments returns equal `Step`s.
- Two interleaved games share no objects except the read-only `Story` (US2-AS7).
