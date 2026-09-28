# Contract: Engine API (`ravel.engine`) — domain layer

Pure functions. No I/O, no callbacks, no module-level mutable state. Same inputs → same outputs
(FR-005, FR-008, FR-016). Types are defined in [data-model.md](../data-model.md).

```python
def start(story: Story) -> Step: ...
def choose(story: Story, state: GameState, location: LocationId) -> Step: ...
def present(story: Story, state: GameState) -> tuple[Output, ...]: ...
def resume(story: Story, saved: SavedGame) -> Step: ...  # 2026-09-28; replaces validate_resumable on the load path
def choice_blocks(
    situation: types.Situation,
) -> tuple[ChoiceBlock, ...]: ...  # 2026-09-28; shared by begin_choices, encode_save, resume
```

**2026-09-28 revision**: `validate_resumable` is **removed**. It existed to hard-refuse a save
whose stack, offered menu, or halted label didn't match what the engine would derive. That job is
now split: `decode_save` still does cheap, story-free shape checks (save-format.md), and `resume`
does the story-dependent part — but by *truncating*, never by raising. Nothing on the load path
raises `InvalidStateError` any more.

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


class InvalidStateError(EngineError):
    ...  # unreachable-state errors from the run loop itself
    # (unknown location, bad ip, bare Choice/GetChoice);
    # no longer raised for loaded saves (2026-09-28) —
    # resume() truncates instead
```

A `ZeroDivisionError`/`TypeError` raised by an author's operation propagates unchanged (a story
bug, not an engine state); the CLI's `--debug` path handles it.

## `present(story, state)`

Re-presents a resting state without running anything, from a `GameState` whose `offered` is
already correct (used by `resume` for the non-empty-stack case; `resume` handles the empty-stack
query case itself since a saved state no longer carries an `offered` to re-derive labels from):
- `WAITING` → `(ChoicesOffered(...labels re-derived from story for state.offered...),)`
- `HALTED` → `(Halted(outcome.label, outcome.dead_end),)`

## `choice_blocks(situation)`

Returns every choice block in `situation`, source order, as `ChoiceBlock(choices, get_choice_ip)`
(data-model.md § Choice blocks, anchors, and saved frames). `begin_choices` (the run loop's
`BeginChoices` handler) is refactored to use this instead of gathering choices inline, so the
exact same source-order scan backs the run loop, `encode_save`'s anchor computation, and
`resume`'s anchor resolution — one definition of "which block is this", not three.

## `resume(story, saved)` — 2026-09-28

Turns a `SavedGame` (from `decode_save`, story-free) into a `Step`, resolving every saved frame
against `story` and **never raising**. This is the whole of what used to be
"`present` after a hard-validated load"; it now does the validating-by-truncating itself.

1. If `saved.status is HALTED`: `saved.stack` is empty by construction (decode-time invariant).
   Build `GameState(qualities=saved.qualities, stack=(), status=HALTED, offered=(), outcome=saved.outcome)`
   and return `Step(state, (Halted(saved.outcome.label, saved.outcome.dead_end),))`. No anchor
   resolution happens for a halted save — there is no stack to resolve, and (2026-09-28) no
   check that `outcome.label` is one of the story's `End` labels: a stale label just loads as
   that halt.
2. Otherwise (`WAITING`), walk `saved.stack` bottom → top. For each `SavedFrame(location, anchor)`:
   - if `story.has_location(location)` is false, or `choice_blocks(story.situation(location))` has
     no block whose `choices` equals `anchor.choices`: **truncate** — stop resolving; this frame
     and every `SavedFrame` above it (in source/save order) are **dropped**.
   - otherwise resolve to the `anchor.ordinal`-th matching block (or the first match if `ordinal`
     is out of range), producing a real `Frame(location, get_choice_ip)`.
3. Every resolved frame except the last (the new top) gets `ip + 1` (mirrors `choose`'s "advance
   past the GetChoice before pushing the child", so a still-valid ancestor frame is correctly
   mid-gather, not re-waiting).
4. If the resolved stack is non-empty: `offered` = the new top frame's resolved block's `choices`
   (already known from step 2, no re-query needed); output via `present`-style
   `ChoicesOffered(...)`.
   If the resolved stack is empty (either `saved.stack` was already empty, or every frame got
   dropped): re-query the story fresh from `qualities` (the same private query the run loop uses
   for empty-stack — a dead end here halts with `Outcome("", dead_end=True)`, same as any query).
5. If any frames were dropped in step 2, prepend `StoryChanged(dropped=<their locations, in the
   order they were dropped, deepest-kept-adjacent first>)` to the outputs. An unchanged story
   (nothing dropped) emits exactly what `present` would have emitted for that state — no
   `StoryChanged`, ever.

**Determinism**: for an unchanged story, `resume(story, decode_save(encode_save(story, s)))`
resolves every frame back to its exact original `ip`, so `.state == s` and `.outputs` matches
`present(story, s)` exactly (FR-025, save-format.md round-trip laws).

## Determinism and isolation

- Menu order pinned by `tests/engine/test_engine_query.py` (FR-011) and documented in VM spec §7.3.
- `choose(story, s, x)` called twice with the same arguments returns equal `Step`s.
- Two interleaved games share no objects except the read-only `Story` (US2-AS7).
