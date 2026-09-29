# Ravel Engine Specification

**Version**: 0.2
**Status**: Describes the shipped engine (`ravel.engine`, `ravel.app`, `ravel.adapters`)

---

## 0. Status and scope

This document describes what the code in `src/ravel/` does today. Version 0.1 of this file was a
design draft for an instruction-set VM (opcodes, an event bus, layered qualities, a JSON IR). That
design was not built; Appendix A summarizes it as history. Where this document and the code
disagree, the code wins and this document has a bug.

What ships:

| Surface | Module |
|---|---|
| Engine API: `start`, `choose`, `present`, `resume` | `ravel.engine.engine` (re-exported by `ravel.engine`) |
| State types: `GameState`, `Qualities`, `Frame`, `Status`, `Outcome`, `SavedGame` | `ravel.engine.state` |
| The read-only compiled story: `Story` | `ravel.engine.story` |
| The seven output types and `Step` | `ravel.engine.outputs` |
| Engine errors (`EngineError` and subclasses) | `ravel.engine.errors` |
| Compiled directive types (`Text`, `Operation`, `Choice`, `BeginChoices`, `GetChoice`, `End`) | `ravel.types` |
| Save format v1: `encode_save`, `decode_save` | `ravel.app.saves` |
| Ports `StorySource`, `SaveStore`; the session `GameSession` | `ravel.app.ports`, `ravel.app.session` |
| Adapters `FileSystemStorySource`, `MemoryStorySource`, `FileSaveStore` | `ravel.adapters` |
| `Environment`, `FileSystemLoader`, `MemoryLoader` | `ravel.environments`, `ravel.loaders` |
| The console adapter `ConsoleUI` | `ravel.cli` |

The detailed contracts live in `specs/001-reentrant-vm/contracts/` (`engine-api.md`,
`save-format.md`, `session-api.md`, `end-directive.md`, `cli.md`) and
`specs/002-spec-compliance/contracts/` (`embedding.md`, `evaluation.md`). This document summarizes
them and links rather than repeating byte-level detail. The authoring language is in
`docs/RAVEL_LANGUAGE_SPEC.md`.

The acceptance tests that pin this behavior are `tests/acceptance/test_us02_engine.py`,
`test_us03_end.py`, `test_us04_save_load.py`, `test_us05_cli.py`, `test_us06_end_to_end.py` and
`test_us06_save_load_property.py`, plus `tests/acceptance/spec_compliance/test_us01_expressions.py`,
`test_us02_constraints.py`, `test_us03_rulebooks.py`, `test_us04_embedding.py`,
`test_us04_determinism_property.py` and `test_us05_docs.py`.

---

## 1. Introduction

The engine plays a compiled Ravel story. The pipeline is:

```
.ravel source → Environment + Loader → compiled rulebook → Story
             → ravel.engine (start / choose / present / resume) → GameSession → adapter
```

Goals:

- **Deterministic.** The same story and the same choices give the same states, outputs and save
  bytes (§7).
- **Savable.** Any resting state encodes to canonical bytes and resumes, even against an edited
  story (§8).
- **I/O-free.** The engine reads no files, clock or randomness and writes nothing. It has no
  mutable module state, no signals and no callbacks.
- **Embeddable.** Every call takes values and returns values, so a host can drive it from a
  console loop, an async server or a stateless HTTP handler (§10).

---

## 2. Domain model

All engine state types are frozen `attrs` classes in `ravel.engine.state`.

**`QualityValue`** is `int | float | str`. The storable domain is: `int` in the signed 64-bit range
(`INT_QUALITY_RANGE`), finite `float`, and `str` with no lone surrogate. `bool` is not a quality
value. Anything else raises `InvalidQualityValueError`.

**`LocationId`** is a `str` naming a situation, namespaced `rulebook::rule` and, for a choice,
`rulebook::rule::choice-slug` (see `Environment.location_separator`).

**`Qualities`** is an immutable map stored as a tuple of `(name, value)` pairs sorted by name.
`get(name)` returns `None` for an unset quality; `set(name, value)` returns new `Qualities` and
validates the value; `as_dict()` returns a fresh `dict`.

**`Frame(location, ip)`** is one situation on the stack and the index of its next directive.

**`Status`** is a `StrEnum`: `RUNNING` (`"running"`), `WAITING` (`"waiting_input"`) and `HALTED`
(`"halted"`). No engine call returns a `RUNNING` state.

**`Outcome(label, dead_end=False)`** says how a halted game ended: an `end` label, or `dead_end=True`
when no situation matched.

**`GameState`** holds `qualities`, `stack` (a tuple of `Frame`), `status`, `offered` (the location
IDs of the current menu) and `outcome`. A waiting state has `outcome=None`; a halted state has an
empty stack and empty `offered`.

**`Story`** (`ravel.engine.story`) wraps the compiled rulebook, read-only and shareable between
games. `situation(location)` returns a `types.Situation` or raises `KeyError`; `has_location`
tests for one; `givens` is the story's initial operations, in order.

**Compiled directives** (`ravel.types`). A `Situation` has an `intro` and a list of `directives`:

| Directive | Meaning |
|---|---|
| `Text(text, sticky, predicate)` | a line of prose, shown when its `{…}` predicate holds |
| `Operation(quality, operator, expression, constraint)` | an `effect:`, or a `given:` |
| `BeginChoices` | starts a run of consecutive `Choice`s |
| `Choice(choice)` | one menu option; `choice` is the target `LocationId` |
| `GetChoice` | ends the run; the engine waits here |
| `End(outcome)` | ends the game with a label |

The compiler inserts `BeginChoices` before and `GetChoice` after each run of `choice:` items. Each
choice's body compiles to its own `Situation` at its own `LocationId`. There is no separate
instruction encoding: the engine runs these objects directly.

---

## 3. Engine API

Four functions in `ravel.engine`. `start`, `choose` and `resume` return a `Step(state, outputs)`,
where `outputs` is a tuple of the §4 types. None of them mutates its arguments.

- **`start(story)`** applies `story.givens` once each (one `QualityChanged` per given), then runs
  from an empty stack, which means a query (§5).
- **`choose(story, state, location)`** checks, in order: a `HALTED` state raises `GameOverError`;
  any other non-`WAITING` state raises `NotWaitingError`; a `location` not in `state.offered`
  raises `NotOfferedError`. Otherwise it advances the top frame past its `GetChoice` (if there is
  a frame), pushes `Frame(location, 0)`, emits `SituationEntered(location)` and runs.
- **`present(story, state)`** runs nothing. It returns `(Halted(...),)` for a halted state, or
  `(ChoicesOffered(...),)` rebuilt from `state.offered` for a waiting one. It returns a tuple of
  outputs, not a `Step`.
- **`resume(story, saved)`** turns a story-free `SavedGame` (from `decode_save`) into a `Step`
  against `story`, and never raises. See §8.

**Errors** (`ravel.engine.errors`), all subclasses of `EngineError`:

| Error | Raised when |
|---|---|
| `NotOfferedError` | `choose` gets a location that isn't in `state.offered` |
| `GameOverError` | `choose` is called on a halted state |
| `NotWaitingError` | `choose` is called on a state that isn't waiting |
| `InvalidOperationError` | an operation's expression or constraint fails (§6); `__cause__` is the `EvaluationError` |
| `InvalidQualityValueError` | an operation's result is outside the storable domain (§2) |
| `InvalidStateError` | a hand-built state names an unknown situation, an out-of-range `ip`, or a stray `Choice`/`GetChoice`; engine-produced states never do |

An error leaves the caller's `state` as it was, since the engine never mutated it.
`GameSession.choose` only assigns the new state after the engine returns.

---

## 4. Outputs

`ravel.engine.outputs` defines seven frozen output types. They are plain values, returned in
`Step.outputs`; nothing is sent over a signal. `Output` is their union.

| Output | Fields | Emitted when |
|---|---|---|
| `TextShown` | `text`, `sticky` | a `Text` directive's predicate holds and its text isn't blank |
| `ChoicesOffered` | `choices` (non-empty tuple of `ChoiceOption(location, label)`) | the engine waits for a choice |
| `QualityChanged` | `name`, `old` (`None` if unset), `new` | a given or an operation runs |
| `SituationEntered` | `location` | `choose` pushes a frame |
| `SituationExited` | `location` | a frame runs past its last directive and is popped |
| `Halted` | `outcome`, `dead_end` | an `End` runs, or a query matches nothing |
| `StoryChanged` | `dropped` (the dropped frames' locations, bottom to top) | `resume` had to drop saved frames that no longer match the story |

A `ChoiceOption` label is the target situation's intro text. `StoryChanged` is never emitted by
`start`, `choose`, or a resume against an unchanged story.

---

## 5. Execution semantics

One engine call runs until the game waits or halts. The run loop (`_Run.run` in
`ravel.engine.engine`) repeats:

1. **Empty stack → query mode.** Query every `Situation` rule against the current qualities
   (`ravel.queries.query`). No match: halt with `Outcome("", dead_end=True)` and emit
   `Halted("", True)`. Otherwise offer every match and wait.
2. **Top frame past its last directive →** pop it and emit `SituationExited`.
3. **Otherwise dispatch on the directive's type:**
   - `Text`: emit `TextShown` if `text.check(qualities)` holds and the text isn't blank; advance.
   - `Operation`: apply it (§6), emit `QualityChanged`; advance.
   - `BeginChoices`: park the frame's `ip` on the matching `GetChoice`, emit `ChoicesOffered` for
     the block's choices, set status `WAITING` and return.
   - `End`: clear the stack, emit `Halted(label, False)`, set status `HALTED` and return, at any
     stack depth.
   - `Choice` or `GetChoice` reached directly: `InvalidStateError`.

**Choice blocks.** A choice menu is not a jump. Choosing pushes the chosen situation on top of the
situation that offered it. When the chosen situation finishes, it pops, and the parent resumes at
the directive after its `GetChoice` (the "gather"). When the stack empties, the loop queries again.

**Query sort.** Query menus sort by the number of predicates on the rule, most first, then by
location ID descending in Python `str` order. More specific rules come first. In-situation menus
keep their source order.

**Predicates.** A rule matches when every predicate holds. A predicate on an unset quality tests
the value 0.

---

## 6. Expressions, operations and constraints at run time

Expressions evaluate against the current qualities. A bare or `[bracketed]` name reads that
quality, and an unset quality reads 0. `value` reads the subject quality's current value (0 if
unset). The grammar, precedence and examples are in the language spec §5; the evaluation contract
is `specs/002-spec-compliance/contracts/evaluation.md`.

**Conditions fail soft.** `Comparison.check` returns false when its comparison raises
`EvaluationError`, and logs nothing. This applies to `when:` predicates and to `{…}` text prefixes.
A condition that cannot be evaluated (for example `X > 10 / Y` with `Y` unset, or `X > Name` with
`Name` a string) is false. So `X > E` and `X <= E` can both be false, and a story whose conditions
all fail reaches a dead end. `Comparison.evaluate` still raises, for tools that want to check a
condition.

**Operations fail loud.** Operations run through `_apply_operation`. `Operation.evaluate` computes
the new value; if applying the operator raises `TypeError` or `ArithmeticError`, it raises
`EvaluationError`, and the engine re-raises that as `InvalidOperationError` with the
`EvaluationError` as `__cause__`. Examples: `X = 100 / Bonus` with `Bonus` unset (division by zero),
`X = Name + 1` with `Name` a string. The result then goes through `Qualities.set`, which raises
`InvalidQualityValueError` (not wrapped) if it's outside the storable domain, such as an `int`
past 64 bits.

**Constraints clamp.** A `min`/`max` constraint (`Constraint.apply`) clamps a numeric result to its
bound, for every operator including `=`. A string result under a constraint raises
`ConstraintError`, an `EvaluationError`, so the engine raises `InvalidOperationError`. Givens are
operations too: `Gold = 50 max 20` starts `Gold` at 20.

Only the operator call is wrapped. A `TypeError` from elsewhere (a broken `QualityLookup`, a term
type with the wrong signature) is a bug and propagates unwrapped.

**Known limits.**

- String length is capped (`MAX_STRING_LENGTH`), enforced on concatenation before the result is built and
  again on storage, so `X *= 2` on a string quality cannot double without bound. The value is in
  `docs/RAVEL_LANGUAGE_SPEC.md` "### E. Limits", the single table of caps.

---

## 7. Determinism guarantee

For a `Story` compiled from the same sources and the same sequence of `choose` locations,
`start`/`choose` return equal `Step`s (equal outputs, equal `GameState`s), and `encode_save`
returns equal bytes. This holds across repeated runs and across freshly compiled `Story` objects.
The engine has no randomness, clock or I/O, and `Qualities` keeps its items sorted, so nothing
depends on insertion order. `tests/acceptance/spec_compliance/test_us04_determinism_property.py`
pins this.

---

## 8. Save format v1

The code is `ravel.app.saves`; the full contract is `specs/001-reentrant-vm/contracts/save-format.md`.

- **`encode_save(story, state)`** takes a waiting or halted `GameState` and returns canonical UTF-8
  JSON bytes: sorted keys, no spaces, no ASCII escaping, a trailing newline. A `RUNNING` state
  raises `InvalidStateError`. Every save starts with `SAVE_MAGIC`.
- The document is `{"format": "ravel-save", "format_version": 1, "state": {...}}`. `state` holds
  `qualities` (an object), `stack`, `status` (`"waiting_input"` or `"halted"`) and `outcome`
  (`null`, or `{"label", "dead_end"}` when halted).
- Saves carry no story identity and no `ip`. Each saved frame is `{"location", "anchor"}`, where the
  `Anchor` names the choice block the frame waits at by its choice targets and an `ordinal` among
  blocks with the same targets. That lets a save survive an edit to the story.
- **`encode_save(story, state)`** enforces the same 1 MiB `MAX_SAVE_BYTES` cap on save: an encoding over it raises
  `SaveTooLargeError` (a `SessionError`) before any store write, so a save that could not be loaded back is never written.
- **`decode_save(data)`** is story-free. It checks size (`MAX_SAVE_BYTES`, 1 MiB), JSON validity
  (no duplicate keys, no `NaN`/`Infinity`), exact key sets, value types, the storable quality
  domain, and that each child frame is one of its parent anchor's choices. It returns a
  `SavedGame` and raises only `LoadRefusedError` subclasses: `SaveCorruptError` or
  `UnsupportedSaveVersionError`.
- **`resume(story, saved)`** resolves the save. A halted save is restored as-is. A waiting save's
  frames resolve bottom to top: a frame whose location is gone, or whose anchor matches no block,
  is dropped with every frame above it, reported by one leading `StoryChanged`. If no frame is
  left, the story is queried fresh from the saved qualities, which may itself dead-end. Givens are
  never re-applied.

Guarantees: for any resting state `s` reached by the engine,
`resume(story, decode_save(encode_save(story, s))).state == s`, and re-encoding gives the same
bytes. Every storable quality value decodes equal to what was encoded and of the same type.

---

## 9. Ports and adapters

`ravel.app` depends on two `Protocol`s in `ravel.app.ports`, never on a concrete adapter:

- **`StorySource`** has `load() -> Story`.
- **`SaveStore`** has `write(name, data) -> str` (returns a display path) and
  `read(name) -> bytes` (reads at most `MAX_SAVE_BYTES + 1` bytes). `OSError` propagates.

Adapters in `ravel.adapters`:

| Adapter | Port | Behavior |
|---|---|---|
| `FileSystemStorySource(directory)` | `StorySource` | compiles the `.ravel` files under `directory` on each `load()` |
| `MemoryStorySource(sources, entry="begin")` | `StorySource` | compiles a mapping of rulebook name to source text; no filesystem access |
| `FileSaveStore(base=None)` | `SaveStore` | atomic write via a temp file and `os.replace`; refuses to overwrite a non-empty file that isn't a ravel save; reads regular files only |

No in-memory `SaveStore` ships; any object with `write` and `read` satisfies the port.

**Loaders.** `Environment` (`ravel.environments`) requires a `loader`: `Environment()` raises
`TypeError`, as does a loader without a callable `load`. `ravel.loaders` provides
`FileSystemLoader(base_path, extension=".ravel")`, which refuses an include that resolves outside
`base_path` (`RulebookNotFound`), and `MemoryLoader(sources)`, which serves a mapping. Both
subclass `BaseLoader`. `Environment.load()` starts at `initializing_name` (default `begin`) and
follows `include:` breadth-first. `Environment.compile_rulebook` gates every loader's
source, shipped or custom: it refuses one over the byte cap (`MAX_RULEBOOK_BYTES`, `RulebookTooLargeError`)
and one nested past `MAX_SOURCE_NESTING_DEPTH` indentation levels before parsing, both as `ParseError`.

**`GameSession`** (`ravel.app.session`) is the one mutable holder. `GameSession(story, saves)`
offers `new_game()`, `choose(location)`, `menu()`, `save(name)` and `load(name)`, and a `state`
property that raises `NoGameError` before any game exists. `load` is `saves.read` →
`decode_save` → `resume`, and raises only `LoadRefusedError` subclasses (`SaveNotFoundError`,
`SaveUnreadableError`, `SaveCorruptError`, `UnsupportedSaveVersionError`). Every method assigns
new state only after the engine or decoder succeeds, so a failed call leaves the game as it was.
`ConsoleUI` in `ravel.cli` is the shipped adapter that renders a session's outputs.

**Story sources are trusted input.** The compiler refuses oversized and deeply nested source with a typed
`ParseError` rather than a raw `RecursionError`: source bytes, indentation nesting, expression length,
operand count, parenthesis nesting, expression depth and choice nesting are all capped. See
`docs/RAVEL_LANGUAGE_SPEC.md` "### E. Limits" for the caps and their errors. A `RecursionError` from the
parser is only a residual backstop, converted to `ParseError` in `Environment.compile_rulebook`. The caps
bound input size, not compile time, so a host that compiles untrusted rulebooks must still isolate
compilation in a separate process with time and memory limits (RT-8).

---

## 10. Host recipes

These are recipes built on the pure API. None of them ships as code.

### 10.1 Realtime (in-process)

Hold one `GameSession` for the player. Call `new_game()` or `load(name)`, render the outputs, then
loop: read a choice from `menu()`, call `choose(location)`, render. This is what `ConsoleUI` does.
Save whenever the game is at rest (waiting or halted).

### 10.2 Async

The engine does no I/O, so a call blocks only for its own CPU time and never awaits anything. Share
one `Story` between all games; it's read-only. Keep one `GameState` per player. Only the
`SaveStore` touches I/O: run a blocking store under `asyncio.to_thread`, or write a store that
calls an async backend from the host side. Because every call returns a new state, concurrent
games never share mutable state.

### 10.3 HATEOAS (stateless server)

Each request carries the save and the chosen location; the response carries the new save, the
outputs, and links for the offered choices. From `specs/002-spec-compliance/contracts/embedding.md`:

```python
def handle(story: Story, save: bytes, location: LocationId) -> tuple[bytes, tuple[Output, ...]]:
    step = engine.resume(story, decode_save(save))
    step = engine.choose(story, step.state, location)
    return encode_save(story, step.state), step.outputs
```

Build the links from `step.state.offered` (or the `ChoicesOffered` output).

**Save integrity is the host's job.** Saves are not tamper-evident: `decode_save` checks shape and
size only, and `resume` accepts any well-formed qualities and stack. If the save bytes travel
through the client (a hidden field, a URL, a cookie), a player can forge any quality. The host must
do one of two things:

1. **Keep saves server-side** behind an opaque id, stored through a `SaveStore`, and send only the
   id to the client.
2. **Authenticate the bytes**: HMAC the save with a key only the server holds, and verify the tag
   before calling `decode_save`.

**The Limits caps are not a compute budget.** The §E Limits caps bound input size (source bytes,
nesting, counts of things), not total compile time or per-turn compute: a story within every cap can
still be slow to load or slow to evaluate. A host running untrusted stories must wrap `Environment.load`
and each engine call (`start`, `choose`, `present`, `resume`) in its own timeout or sandbox.

The engine ships neither. `choose` still refuses a location that isn't in `state.offered`
(`NotOfferedError`), so a forged location can't skip the menu, but a forged save can.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| Anchor | a saved frame's reference to its choice block, by targets and ordinal |
| Choice block | a run of `Choice` directives between `BeginChoices` and `GetChoice` |
| Dead end | a query that matches no situation; the game halts with `dead_end=True` |
| Directive | one compiled item in a situation (§2) |
| Frame | a situation on the stack plus its next directive index (`ip`) |
| Gather | the parent situation's directives after a choice block, run when the chosen situation pops |
| Given | an operation applied once by `start` |
| Location | the namespaced ID of a situation |
| Output | one of the seven values an engine call returns (§4) |
| Quality | a named `int`, `float` or `str` value in `Qualities` |
| Query mode | what the engine does with an empty stack: offer every matching situation |
| Situation | a compiled rule body: intro text plus directives |
| Story | the compiled rulebook, read-only |

---

## Appendix A. Design history

Version 0.1 of this document (2025) specified a different design. None of it shipped.

- **Instruction set and codegen** (*not planned*). 0.1 compiled situations to opcodes (`PUSH`,
  `POP`, `DISPLAY_TEXT`, `SET_QUALITY`, `BRANCH_IF`, `JUMP`, `YIELD`, `HALT`, `QUERY_SITUATIONS`,
  …) run by a `step()`/`run_until_yield()` executor. The engine instead dispatches on compiled
  directive types (001 PD-03), and the directive list has no jumps.
- **Serialized JSON IR** (*deferred*). 0.1 defined a JSON schema for compiled rulebooks,
  expressions, predicates and constraints. The compiled rulebook stays an in-memory `dict`.
- **Layered qualities** (*deferred*). 0.1 resolved qualities through `global`, `player`, `session`
  and `location` layers with write targeting. The engine has one flat `Qualities` map.
- **Event bus** (*not planned*). 0.1 published typed events to subscribers with a
  `pending_events` queue. The engine returns output values instead (§4).
- **Frame-local state** (*deferred*). 0.1's `StackFrame` carried `local_state`; `Frame` has only
  `location` and `ip`.
- **Execution modes** (*not planned as code*). 0.1's realtime, HATEOAS and hybrid runners became
  the recipes in §10.
- **The 0.1 `AT-*` acceptance tests** were never run and are dropped; §0 names the real ones.

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2025 | Instruction-set VM design draft |
| 0.2 | 2026-09-28 | Rewritten to describe the shipped engine; 0.1 design moved to Appendix A |
