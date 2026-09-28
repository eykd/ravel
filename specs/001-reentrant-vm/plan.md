# Implementation Plan: Re-entrant VM with Save/Load and a Winnable Cloak of Darkness

**Branch**: `001-reentrant-vm` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-reentrant-vm/spec.md`
**Diagnosis**: [research.md](./research.md) §1–§5 (D1–D20); planning decisions appended as
`## Planning Decisions (sp:03-plan)` (PD-01 … PD-20).

## Summary

Upgrade to syml 1.0 (re-indent every example, fixture, and spec example), then replace the
queue-and-signals VM with a pure, re-entrant engine built to `docs/RAVEL_VM_SPEC.md`: frames of
`(location, ip)`, a YIELD at every choice block, HALT via a new `- end:` directive, and "empty
stack = query mode". The engine is two pure functions, `start(story)` and
`choose(story, state, location)`, each returning a new immutable `GameState` plus a tuple of
plain-value outputs. An application-layer `GameSession` adds save/load over two ports (story
source, save store); the CLI becomes a thin click adapter over the session. The old `ravel.vm`
package and `blinker` are deleted.

## Technical Context

**Language/Version**: Python 3.14 (unchanged floor, `.python-version`)
**Primary Dependencies**: attrs, click, colorclass, parsimonious 0.10, python-slugify,
syml `>=1.0,<2` (was `>=0.6`). **Removed**: blinker. **Dev added**: hypothesis.
**Storage**: save files, canonical JSON on the local file system (adapter only)
**Testing**: pytest + pytest-cov (100% branch), hypothesis (property test). Acceptance tests are
plain pytest end-to-end tests under `tests/acceptance/` (no Gherkin; PD-15)
**Target Platform**: macOS/Linux terminal (`ravel run`), plus library consumers of `ravel.engine`
/ `ravel.app`
**Project Type**: library + console script
**Performance Goals**: none beyond interactive latency; a Cloak turn is microseconds. The 200-case
property test must finish in < 30 s locally
**Constraints**: domain layer pure (no I/O, no blinker, no module-level mutable state); 100% branch
coverage; ruff/mypy/pre-commit clean; saves byte-deterministic
**Scale/Scope**: ~6 new modules in `ravel.engine`, 3 in `ravel.app`, 2 in `ravel.adapters`,
rewritten `cli.py`, one new directive (`end`), 6 deleted `vm/` modules, 4 deleted test files

All former NEEDS CLARIFICATION items are resolved in research.md PD-01 … PD-20.

## Brainstorm Context

**Source**: [specs/brainstorms/2026-09-27-reentrant-vm-requirements.md](../brainstorms/2026-09-27-reentrant-vm-requirements.md)

### Key Decisions Carried Forward

- Build to `docs/RAVEL_VM_SPEC.md` rather than patch the VM: D2/D3 are structural.
- The engine API and saves use location IDs, never menu indices (menu numbering is CLI-only).
- Story identity is a hash of the compiled rulebook, not file mtimes.
- Blinker leaves the core; constitution VI/VII need amendment wording (below).
- `- end: <outcome>` syntax; `save [FILE]` / `load [FILE]` / `--load FILE` CLI UX;
  `rooms.ravel` deleted; menu order kept and pinned.

### Deferred Questions (resolved during planning)

- Identity hash derivation / source positions → PD-06: SHA-256 over a canonical JSON encoding of
  the compiled rules, locations, and givens; positions and `about:` metadata excluded.
- Explicit instructions vs interpreting `BeginChoices`/`Choice`/`GetChoice` → PD-03: interpret the
  existing directives; `GetChoice` is the YIELD point and the frame ip rests on it.
- Warn on directives after `end` → PD-10: no warning; unreachable directives are simply never run.
- Is blinker needed anywhere → PD-12: no; dropped from runtime dependencies.
- syml 1.0 on the index vs path source → PD-01: PyPI `syml>=1.0,<2`; fallback is a git tag
  source in `[tool.uv.sources]`, never a path source.

### Explicit non-goals (scope boundaries)

Quality layers (VM spec §3), HATEOAS/hybrid modes (§7.5), explicit IR opcodes/rulebook JSON
serialization (§6.2, §8.2), `<>` glue rendering (flag carried only), visit counts, once-only
choices, RNG, conditional `end`, menu-order redesign (D17), Cloak semantics beyond the two `end`s
(D20), latent syml 1.0 semantics (diagnosis §1.3).

## Constitution Check

_GATE: evaluated before Phase 0 and re-checked after Phase 1 (constitution v1.1.0)._

| Principle | Status | Notes |
|---|---|---|
| I. TDD (NON-NEGOTIABLE) | PASS | Every task starts RED, committed via `.venv/bin/python -m tools.commit_red <task-id>` before implementation. US1 is a refactor-under-green (re-indent) whose RED is the syml-1.0 bump itself failing 37 tests. Acceptance tests are written RED first per story. |
| II. Type Safety | PASS (tightened) | New packages go strict per-module (see Typing below). II's prose ("`check_untyped_defs` not set") becomes stale → PATCH wording in the amendment below. |
| III. Coverage & Lint | PASS | 100% branch kept; deleted tests only cover deleted code; no new `# pragma: no cover`. |
| IV. Spec discipline | PASS | See Spec Conformance; the `end` directive and menu-order rule land in the specs in the same commits as the behavior. |
| V. Simplicity / YAGNI | PASS | No new runtime dependency (one removed). `End` joins `types.py`. No PEG change: `end` dispatches in `compile_directive` like `choice`/`effect`. Engine interprets existing directives instead of adding an IR (PD-03). |
| VI. Public API Stability | **BREAK (listed)** | See below. |
| VII. Clean Architecture | PASS | v1.1.0 is already mechanism-neutral. Its file list (`vm/machines.py` …) goes stale → path update in the amendment. |

### Principle VI public-API breaks

| Removed / changed surface | Replacement |
|---|---|
| `ravel.vm.events` (all frozen attrs events, incl. `display_text`, `display_choice`, `waiting_for_input`, `quality_changed`, `enter_state` …) | `ravel.engine.outputs` plain values (`TextShown`, `ChoicesOffered`, `QualityChanged`, `SituationEntered`, `SituationExited`, `Halted`) returned, not sent |
| `ravel.vm.signals` (`Signals`, `SIGNAL`, named blinker signals) | none: outputs are return values |
| `waiting_for_input.send_input` callable | `ravel.engine.choose(story, state, location)` / `GameSession.choose(location)` |
| `ravel.vm.machines.VirtualMachine`, `ravel.vm.states.*`, `ravel.vm.runners.*` (`StatefulRunner`, `QueueRunner`) | `ravel.engine.start/choose/present`, `ravel.app.GameSession` |
| `ravel.cli.ConsoleRunner` | `ravel.cli.ConsoleUI` over `GameSession` |
| `blinker` runtime dependency | dropped |

Unchanged: `Environment.load()`/`load_rulebook()`, `BaseLoader.load/get_source`, the compiled
rulebook dict shape (gains the `End` directive type and a `CompiledRulebook` TypedDict annotation,
same keys), `Source`/`Pos`.

**Rejected non-breaking alternative**: keep `ravel.vm.events`/`signals` as a compatibility façade,
re-emitting engine outputs as the old events over blinker. Rejected because (a) the old events
carry live `State` objects and a `send_input` callable (D7, D8), which the pure engine cannot
produce without re-creating the defects; (b) the named global signals are the cross-talk bug D6
itself; (c) there are no known external consumers (version `0.1.dev0`, never released), so the
façade is cost with no caller; (d) a façade keeps blinker as a runtime dependency (Principle V).

### Proposed constitution amendment v1.1.0 → v1.2.0 (MINOR) — needs David's sign-off

- **VI**: public surface becomes `Environment.load()`/`load_rulebook()`, the `Loader` interface,
  the compiled rulebook shape, `Source`/`Pos`, **`ravel.engine`'s `start`/`choose`/`present`, its
  state and output value types, `ravel.app.GameSession`, and the save-file format (version 1)**.
- **VII**: domain core = `types.py`, `queries.py`, `compiler/`, `ravel.engine`; application =
  `ravel.app`; adapters = `ravel.adapters`, `cli.py`, `loaders.FileSystemLoader`, `environments.py`.
- **II**: state that `ravel.engine.*`, `ravel.app.*`, `ravel.adapters.*`, `ravel.cli`,
  `ravel.types`, `ravel.queries` are strict per-module; the rest stays "stay clean".

MINOR, not MAJOR (the spec anticipated MAJOR): no principle is removed or redefined; each keeps
its rule and only its enumerated file/surface list changes. It lands as its own commit
(`docs: amend constitution to v1.2.0 (...)`) in the first engine task, per the Amendment Procedure.

**Post-design re-check (after Phase 1)**: PASS. Contracts keep the domain free of I/O imports
(enforced by `tests/engine/test_layering.py`, SC-008); no new runtime dependency; the only break
is the listed VI surface.

## Spec Conformance

| Change | Spec section | Changes the spec? |
|---|---|---|
| syml 1.0 re-indent of examples | LANGUAGE §all examples (lines ~76, 277, 347, 452–493, 561, 625–631, 704) | Yes: examples re-indented; add the key rule `[a-z][a-z0-9_-]*` to §8.3 |
| `- end: <outcome>` directive | LANGUAGE §9 Directives, §10.2 YAML structure, §11.2 Execution model | Yes: new directive documented |
| Pure engine, frames `(location, ip)`, YIELD at choice block, implicit pop, empty stack = query | VM §2.3 StackFrame (no `local_state`), §4.5 YIELD/HALT, §7.2–7.4 | Yes: mark implemented vs deferred; frame is `(location, ip)` only |
| Menu order rule | VM §7.3 ("sort by predicate_score descending") | Yes: add tie-break "then location ID descending" and pin it |
| Outputs replace events | VM §5 Event schema | Yes: §5 rewritten to the six output kinds; `timestamp`/`sequence`, `StackPushed/Popped`, `ChoicesBegin/End`, `WaitingForInput` marked not implemented |
| Save format | VM §6.3 VMState schema | Yes: replaced by save format v1 (contracts/save-format.md); layered qualities deferred |
| Instruction set §4 / IR §6.2 / §8.2 codegen | VM §4, §6.2, §8.2 | Marked **deferred**: engine interprets compiled directives (PD-03) |
| Quality layers §3, HATEOAS §7.5, ports §9 | VM §3, §7.5, §9 | Marked deferred; §9 replaced by the two ports actually built |

Earlier decision records: `docs/RAVEL_*_SPEC.md` are untracked "0.1 Draft" with no git history
(`git log` empty), so no prior decision constrains the design; research.md D1–D20 is the record.

## Architecture & Module Layout

```text
src/ravel/
├── types.py            # + End(outcome); annotated; CompiledRulebook/Ruleset TypedDicts
├── queries.py          # unchanged semantics; annotated
├── compiler/directives.py  # + "end" dispatch → types.End
├── environments.py, loaders.py, parsers.py, grammars.py  # unchanged (syml.parse switch only)
├── engine/             # DOMAIN — pure; imports only stdlib (hashlib, json, enum, typing), attrs, ravel.types, ravel.queries
│   ├── __init__.py     # re-exports the public engine API
│   ├── story.py        # Story (compiled rulebook + identity), fingerprint()
│   ├── state.py        # QualityValue, LocationId, Qualities, Frame, Status, Outcome, GameState
│   ├── outputs.py      # TextShown, ChoiceOption, ChoicesOffered, QualityChanged, SituationEntered, SituationExited, Halted, Output
│   ├── engine.py       # start(), choose(), present(), validate_resumable(); private _Run interpreter
│   └── errors.py       # EngineError, NotOfferedError, GameOverError, NotWaitingError, InvalidQualityValueError, InvalidStateError
├── app/                # APPLICATION
│   ├── __init__.py
│   ├── ports.py        # StorySource, SaveStore (Protocols)
│   ├── saves.py        # SAVE_FORMAT, SAVE_FORMAT_VERSION, encode_save(), decode_save(), LoadRefusedError family
│   └── session.py      # GameSession (new_game, choose, save, load, state, menu)
├── adapters/           # ADAPTERS
│   ├── __init__.py
│   ├── story_source.py # FileSystemStorySource (Environment + FileSystemLoader → Story)
│   └── save_store.py   # FileSaveStore (atomic write, read bytes)
└── cli.py              # click adapter: `main` group, `run DIR [--load FILE]`, ConsoleUI
```

**Deleted**: `src/ravel/vm/` entirely (`__init__.py`, `machines.py`, `states.py`, `events.py`,
`signals.py`, `runners.py`); `tests/test_vm_states.py`, `tests/test_vm_machine.py`,
`tests/test_runners.py`, runner parts of `tests/test_cli.py` (TestConsoleRunner*,
TestRunCommand, TestGetInput; TestMain/TestHandleException survive, adapted);
`examples/cloak/rooms.ravel`. **Dependency removed**: `blinker`.

**Why a new `ravel.engine` name instead of rewriting `ravel.vm` in place** (PD-02): nothing of the
old package survives, a new name makes stale imports fail loudly, and it lets the old package be
deleted in one commit once the CLI switches over.

**Dependency rule** (enforced by `tests/engine/test_layering.py`, an AST import scan):
`ravel.engine` may import only stdlib `{__future__, abc, collections, dataclasses, enum,
functools, hashlib, itertools, json, math, operator, typing, types}`, `attrs`/`attr`,
`ravel.types`, `ravel.queries`, `ravel.utils`, and itself (relative imports resolved). It must not
import `blinker`, `click`, `colorclass`, `os`, `io`, `pathlib`, `sys`, `logging`, `ravel.app`,
`ravel.adapters`, `ravel.cli`, `ravel.environments`, `ravel.loaders`. `ravel.app` must not
import `ravel.adapters`, `ravel.cli`, `click`, `os`, `pathlib`. (`ravel.queries` uses `logging`;
it is imported, not scanned: its debug logging is inert and pre-existing.)

### Engine execution model (PD-03, PD-04, PD-05)

- `Frame(location, ip)`; `ip` indexes `Situation.directives` (index 0 = the tail text).
- Run loop (inside one call): top frame; if `ip >= len(directives)` → pop (always, FR-010), emit
  `SituationExited`; else dispatch on the directive type:
  - `Text` → if predicate passes and text non-blank, emit `TextShown(text, sticky)`; ip+1.
  - `Operation` → apply, validate the result type, emit `QualityChanged`; ip+1.
  - `BeginChoices` → collect the following `Choice` directives up to `GetChoice`; set ip to the
    `GetChoice` index; status `WAITING`; `offered` = their locations; emit `ChoicesOffered`;
    **return** (YIELD, ip rests on `GetChoice`, FR-009).
  - `End` → status `HALTED`, outcome `Outcome(label, dead_end=False)`, stack and offered cleared,
    emit `Halted`; **return** (FR-018).
- Empty stack → query mode: `queries.query("Situation", …)` (order: predicate count desc, then
  location ID desc); none → halt with `Outcome("", dead_end=True)`; else offer them and return.
- `choose`: validate (halted → `GameOverError`; not waiting → `NotWaitingError`; not offered →
  `NotOfferedError`; state untouched). If the stack is non-empty, set the top frame's ip to
  `GetChoice + 1` (so the gather runs after the child pops). Push `Frame(location, 0)`, emit
  `SituationEntered`, run.
- `start`: apply givens in order to empty qualities (exactly once, FR-014), emitting
  `QualityChanged`, then run from the empty stack.

### Typing (FR-035, SC-007)

`pyproject.toml` changes:

```toml
[[tool.mypy.overrides]]
module = ["parsimonious.*", "colorclass.*", "slugify.*"]   # syml.* removed (FR-003)
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["ravel.engine.*", "ravel.app.*", "ravel.adapters.*", "ravel.cli", "ravel.types", "ravel.queries", "ravel.utils.*"]
check_untyped_defs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_any_generics = true
warn_return_any = true
strict_equality = true
```

`disallow_untyped_calls` is deliberately **not** set: the adapters call `Environment`/compiler
functions that stay unannotated. `Environment.load()`/`load_rulebook()` get return annotations
(`CompiledRulebook`) so the adapter boundary is typed. `tests/` stays unchecked (Principle II).

### Test layout

```text
tests/
├── engine/  test_state.py test_outputs.py test_story.py test_engine_*.py test_layering.py
├── app/     test_saves.py test_session.py
├── adapters/ test_story_source.py test_save_store.py
├── test_cli.py            # rewritten (ConsoleUI + CliRunner); TestMain kept
├── test_compiler_end.py   # end directive compile
├── fixtures/stories/mini/begin.ravel   # gather, dead end, `+=` given, end-in-choice (FR-033)
└── acceptance/  (see below)
```

`pyproject.toml` registers the marker: `markers = ["acceptance: end-to-end user-story tests"]`.

## Delivery Order (fixed)

1. **US1 — syml 1.0** (hard prerequisite, its own commits, suite green at 100% branch before any
   engine code): bump `syml>=1.0,<2`, relock, re-indent `examples/**` (commit the existing
   whitespace-only working-copy re-indent of `taxi/mail.ravel` as-is; see Edge Cases), 19+
   inline fixture lines, spec examples; drop
   `syml.*` from the mypy override; delete `rooms.ravel`; optionally `syml.parse(...)`. SC-009
   one-time check: capture 0.6.2 `as_data()` dumps into the scratchpad **before** the bump,
   compare after, record the result in the commit message. Not a permanent test.
2. **US2 — engine** (`ravel.engine`), plus constitution amendment commit.
3. **US3 — `end` directive** (`types.End`, compiler dispatch, engine HALT, Cloak edits, language spec).
4. **US4 — save/load** (`ravel.app`, `ravel.adapters.save_store`).
5. **US5 — CLI** (rewrite `cli.py`; then delete `ravel/vm/`, old tests, `blinker`).
6. **US6 — end-to-end** (Cloak routes, property test, CLI transcript).
7. Docs (FR-038): CLAUDE.md architecture, VM spec implemented/deferred marks + menu rule,
   language spec `end`, README run/save/load. Each lands with the story that changes the behavior.

## Acceptance Test Strategy

Plain pytest end-to-end tests (PD-15), marked `@pytest.mark.acceptance`, each test docstring
naming its spec scenario (e.g. `"""US2-AS3: gather runs only after the chosen sub-situation."""`).
They drive the public surface only: `ravel.engine`, `ravel.app.GameSession` with the real
`FileSystemStorySource` and a `FileSaveStore` on `tmp_path`, or `click.testing.CliRunner` for the
CLI. Cloak scripts choose by location ID, never by menu position.

| User Story | Acceptance test file | Drives | Scenarios |
|---|---|---|---|
| US1: syml 1.0 | `tests/acceptance/test_us01_syml_upgrade.py` | `Environment` over every `examples/*` dir; pyproject check for the removed override | 3 |
| US2: pure engine | `tests/acceptance/test_us02_engine.py` | `ravel.engine` on Cloak + `tests/fixtures/stories/mini` | 8 |
| US3: end directive | `tests/acceptance/test_us03_end.py` | engine on mini + Cloak; spec-doc grep for `end` in §9/§10.2/§11.2 | 6 |
| US4: save/load | `tests/acceptance/test_us04_save_load.py` | `GameSession` + `FileSaveStore(tmp_path)` | 6 |
| US5: CLI | `tests/acceptance/test_us05_cli.py` | `CliRunner().invoke(main, ["run", …], input=…)`, `monkeypatch.chdir(tmp_path)` | 8 |
| US6: end to end | `tests/acceptance/test_us06_end_to_end.py` (routes + CLI transcript), `tests/acceptance/test_us06_save_load_property.py` (hypothesis, `max_examples=200`, `deadline=None`, `derandomize=True`, `database=None`; in-memory save store) | session + CLI | 4 |

US1-AS1's "equals the 0.6.2 parse" half is the one-time SC-009 check (not permanent, CI has no
0.6.2); the permanent test asserts every example loads.

## Diagnosis Traceability (D1–D20 → fix → proving test)

| # | Fix in this design | Proving test |
|---|---|---|
| D1 double begin | `start()` is the only place givens run; `ConsoleUI` renders the session's outputs once; no `while True` re-run | US2-AS1 (givens once), US5-AS1 (menu shown once), mini `Count += 1` → 1 |
| D2 no stop at choice | `BeginChoices` parks ip on `GetChoice` and returns (YIELD) | US2-AS2, US2-AS3 (gather not run before `choose`) |
| D3 queue-dependent pop | `ip >= len(directives)` pops unconditionally; no queue exists | US2-AS4 |
| D4 event order | `_Run` appends outputs in execution order; `SituationEntered` precedes the child's text | US2-AS3 exact output tuple |
| D5 merged menus | one `offered` tuple per state; `choose` validates against it | `NotOfferedError` when choosing a location from an earlier menu (`begin::intro` while `press-onward` is offered) |
| D6 global signals | no signals, no module-level mutable state | US2-AS7 interleaved games; layering test forbids `blinker` |
| D7 `send_input` callable | input is `choose(story, state, loc)`; states are immutable, so a "stale" state just yields the same `Step` again | `choose` twice on one state → equal `Step`s, original state unchanged |
| D8 live state in events | outputs are frozen plain values | US2-AS8 deep type walk (exact `str`/`int`/`float`/`bool`/`None`/tuple) |
| D9 wrong annotations | strict per-module mypy (Typing) | `uv run mypy` in CI |
| D10 cannot end | `- end:` → HALT | US3-AS1…AS5 |
| D11 empty-menu soft lock | zero query matches → dead-end halt; in-situation blocks are never empty (compiler) | US2-AS6, US5-AS6 dead-end line |
| D12 index semantics | location IDs everywhere; menu numbers exist only in `ConsoleUI` | US5-AS2; saves hold IDs (US4-AS1) |
| D13 givens alias live dict | givens fold over a fresh immutable `Qualities()` | covered by D1 tests |
| D14 `IndexError` as control flow | explicit bounds checks; layering test also rejects `except IndexError` / bare `except` in `ravel.engine` | `test_layering.py` |
| D15 broken runner base class | no runner hierarchy; `ConsoleUI` composes `GameSession` | `tests/test_cli.py` |
| D16 glue ignored | still ignored: explicit non-goal; the flag is carried on `TextShown.sticky` | `TextShown` carries `sticky` (unit) |
| D17 menu tie order | kept, documented (VM §7.3), pinned | `tests/engine/test_engine_query.py` |
| D18 mixed concerns | `Story` (immutable data) / `GameState` (play state) / outputs (values) / session (the one mutable holder) | layering test |
| D19 orphan `rooms.ravel` | deleted in US1 | US1 acceptance (file absent, every example loads) |
| D20 shared `Bar` quality | out of scope (story semantics); only the two `end`s are added | US6 routes pin current behavior |

## Security Considerations

Threat model: a single local player at their own terminal (no privilege boundary), plus a save
file that may come from someone else (shared, hand-edited, truncated, or hostile). Saves are
**not** integrity-protected: editing qualities to cheat is allowed by design. The load checks exist
so no save can crash the CLI, soft-lock the engine, or smuggle control sequences to the terminal.

### Input validation (save decoding, `contracts/save-format.md`)

- **Size cap**: `decode_save` refuses `len(data) > MAX_SAVE_BYTES` (1 MiB) before parsing;
  `FileSaveStore.read` reads at most `MAX_SAVE_BYTES + 1` bytes and refuses non-regular files
  (FIFOs, devices, directories: `load /dev/zero` must not hang or exhaust memory).
- **Strict JSON**: bytes are decoded as strict UTF-8 first (no UTF-16/32 auto-detection, a BOM is
  refused), then `json.loads(text, parse_constant=<reject>, object_pairs_hook=<reject duplicate
  keys>)`. `NaN`/`Infinity` and duplicate keys (`{"format_version":1,"format_version":2}`) are
  `SaveCorruptError`. `RecursionError` (deeply nested arrays) and `ValueError` (e.g. a >4300-digit
  int) raised by the parser are caught and mapped to `SaveCorruptError`.
- **Types**: `bool` is refused everywhere an int is expected (`format_version`, `ip`, quality
  values); quality names and values go through the same `Qualities` validation as the engine
  (finite floats, bounded ints, and **no lone surrogates** in any name or string value).
- **Whole-stack invariants** (not just the top frame): see Edge Cases → Resting-state invariants.
- **Outcome labels**: a halted save's `outcome.label` must be one of the story's compiled `End`
  labels (`dead_end: true` requires `label == ""`). This removes the only place a save could inject
  free text that the CLI prints verbatim.
- **Exception containment**: every exception raised while decoding or validating a save —
  including `TypeError`/`ValueError`/`ZeroDivisionError` from re-deriving the query menu over
  tampered quality types (`Bar = "x"` makes `Bar >= 2` raise) — surfaces as a `LoadRefusedError`
  subclass (chained). The CLI's `load` handler catches only `LoadRefusedError`, so anything else
  would kill the live game and break SC-006.

### Terminal output (CLI)

- Strings that can originate from a save (quality names and values in the `s` listing, locations
  and values quoted in error messages) are rendered with `repr()`, which escapes control
  characters. Story text, labels, and outcome lines come from the compiled story (trusted author
  content, re-derived on load) and print verbatim.

### File-system writes (`save FILE`)

- The filename is the rest of the line after the command word, stripped; no quoting, no `~`
  expansion; relative paths resolve against the current directory; absolute paths are allowed (the
  player is the file owner).
- **Clobber guard**: `FileSaveStore.write` replaces an existing file only if it is empty or starts
  with the canonical save prefix `SAVE_MAGIC = b'{"format":"ravel-save"'` (every v1 save starts with
  it: `sort_keys` puts `format` first). Otherwise it raises `FileExistsError` and the CLI prints
  `Could not save: <path> exists and is not a ravel save`. This stops `save pyproject.toml` or
  `save examples/cloak/begin.ravel` from destroying files. The guard applies to every name,
  including the default: US5-AS3's "overwriting any existing file" is read as "any existing
  save" (a foreign `ravel-save.json` is refused, not clobbered); its overwrite test uses an
  existing save file.
- Atomic write: `tempfile.mkstemp(dir=target.parent)` + `os.replace`; the temp file is removed if
  anything fails before the replace; the new file gets mode `0o666 & ~umask` (not mkstemp's
  `0o600`). `os.replace` onto a symlink replaces the link, never its target.

## Edge Cases & Error Handling

### Resting-state invariants (`engine.validate_resumable`)

Checked for the **whole stack**, bottom → top, so a hand-edited save can never replay an intro,
reach an unhandled directive, or index out of range:

- every frame location is a `Situation` location in the story, and the **bottom** frame is a
  `Situation` *rule* (queryable), since only a query menu can start a stack;
- every **non-top** frame `f[i]` has `1 <= ip <= len(directives)` with `directives[ip - 1]` a
  `GetChoice`, and `f[i+1].location` is one of that choice block's `Choice` locations (the frame
  above is a child that frame really offered);
- the **top** frame's ip indexes a `GetChoice`, and `offered` equals that block's locations in
  source order;
- an empty stack while `WAITING` requires `offered` to equal the re-derived query menu;
- `HALTED` ⇔ `outcome` set ⇔ `stack == () and offered == ()`; the label rule above.

### Engine robustness

- `choose` trusts its input state (it comes from `start`/`choose`/`decode_save`) and does not
  re-run `validate_resumable`, but every "impossible" condition — an unknown location, an ip past
  the end of a block, a bare `Choice`/`GetChoice` reached by the run loop, an unknown directive
  type — raises `InvalidStateError`, never `IndexError`/`KeyError`. These branches are covered by
  tests that pass hand-built states.
- **Quality range**: `int` quality values must satisfy `-(2**63) <= v < 2**63`
  (`InvalidQualityValueError` otherwise). Unbounded ints would make `json.dumps` raise `ValueError`
  past 4300 digits (a `save` crash) and lose precision in any non-Python save reader.
- **Surrogate-free strings**: every quality name and every `str` value must be UTF-8 encodable,
  i.e. contain no code point in U+D800–U+DFFF (`InvalidQualityValueError` otherwise). A save that
  is pure ASCII can still carry `"\udc80"` as a JSON escape: strict UTF-8 decoding accepts it,
  `json.loads` turns it into a lone surrogate, and the next `encode_save` raises
  `UnicodeEncodeError` (a `ValueError` the CLI's `save` handler does not catch), killing the live
  game. The invariant this buys: **any `GameState` that passes validation encodes without
  raising**, so `cli.md`'s narrow `except` stays correct. Story text cannot produce a surrogate
  (source files are strict UTF-8), so the engine branch is covered with a hand-built
  `Qualities.set`.
- Author errors in an operation or predicate (`TypeError`, `ZeroDivisionError`) and
  `InvalidQualityValueError` propagate from `choose`; the session keeps the previous state; the
  CLI treats them as unexpected errors (`handle_exception`, `--debug` → pdb, exit 1).

### Menus

- Query menus: predicate count descending, then location ID descending by Python `str` ordering
  (code points, not locale). In-situation menus: the block's `Choice`s in source order (no sort).
- Two choices in one block whose labels slugify identically compile to one location (the
  compiler's `merge_dicts` keeps the last body). Pre-existing; not fixed here; noted in the
  language spec as a known limitation.
- `present()` after `load` shows only the menu (or halt line), not the text that preceded it.
  Accepted UX (US4-AS2): the save stores no transcript.

### Inherited language gaps (not fixed; documented)

The rewrite interprets existing compiled directives and inherits three latent gaps that no example
triggers: `min`/`max` constraints are parsed but never applied (LANGUAGE §7.3); the `value`
keyword compiles to the `types.VALUE` class and never evaluates to the quality's value (§4.3); a
`[Quality]` reference in an expression yields the quality's *name*. The engine applies operations
through one private `_apply_operation` choke point so a follow-up can fix them behind an
`IR_VERSION` bump; any operation that yields a non-quality value (e.g. the `VALUE` class) raises
`InvalidQualityValueError`. The VM spec marks all three "not implemented".

### Examples under syml 1.0 (US1)

The committed `examples/taxi/mail.ravel` **fails** under syml 1.0 (verified: `OutOfContextNodeError`
at 17:4); only the uncommitted working copy parses. That working-copy diff is whitespace-only
(`git diff -w` is empty) and is exactly the item-17 re-indent, so US1 commits it as-is. At
implementation time, re-check `git diff -w examples/taxi/mail.ravel` is still empty; if not, stop
and re-indent HEAD's version instead of committing someone else's content change. Without this,
the permanent "every example loads" test passes locally and fails in CI.

## Test Strategy Hardening

- **Type-aware oracles.** `1 == 1.0` and `0.0 == -0.0` in Python, so `GameState`/output equality
  cannot see type drift. Round-trip and property tests compare `encode_save` bytes of every
  resting state and `repr()` of output tuples (attrs reprs distinguish `1` from `1.0`), not just
  `==`. The save-format law is stated as "equal bytes ⇒ equal states", not "iff".
- **Property test mechanics.** Hypothesis rejects function-scoped fixtures (`tmp_path`) under
  `@given` (`HealthCheck.function_scoped_fixture`), so the property test uses an in-memory
  `SaveStore` fake; `FileSaveStore` is covered by its own adapter tests. Settings add
  `database=None` (no `.hypothesis/` writes; also add it to `.gitignore`). The resumed session uses
  a **second, independently compiled** `Story` of Cloak, so compile nondeterminism would show up.
  The split point is drawn with `st.data()` after the uninterrupted run fixes the path length.
- **Identity stability tests** (`tests/engine/test_story.py`): same id for (a) Cloak copied to a
  different absolute directory, (b) a whitespace/comment-only edit, (c) a subprocess run under
  `PYTHONHASHSEED=0` and `=1`; different id for a one-character text edit and for a changed given.
- **Coverage of exhaustive dispatch.** No `assert_never` default branches that coverage cannot
  reach and no new `exclude_also` patterns: each `match` ends in a `case _:` that raises a real
  error and is covered by a test passing a foreign object (tests are not type-checked).
- **Other branches needing deliberate tests**: `KeyboardInterrupt` via the injected `read_line`;
  atomic-write failure (monkeypatched `os.replace`) removes the temp file; clobber guard (empty
  file, save file, foreign file); `FileSaveStore(base=None)` → cwd; non-regular file and oversize
  reads; each `validate_resumable` rule; each decode step.
- **Surrogate tests**: `decode_save` refuses a lone high (`"\ud800"`) and a lone low
  (`"\udc80"`) surrogate, both as a quality value and as a quality name (`SaveCorruptError`), and
  **accepts** a valid pair escape (`"\ud83d\ude00"` → one astral character), which must
  round-trip byte-identically; `Qualities.set("q", "\udc80")` raises `InvalidQualityValueError`.
- **Layering test**: resolves relative imports (`from ..app import x`) against the module's
  package, scans `import a.b` and `from a import b` forms, and uses the allowlist
  `{__future__, abc, collections, dataclasses, enum, functools, hashlib, itertools, json, math,
  operator, typing, types}` + `attrs`/`attr` + `ravel.types`, `ravel.queries`, `ravel.utils`, and
  `ravel.engine` itself.

## Typing Pitfalls (Python 3.14, attrs 26, mypy 2.x)

- Keep `order=True` on `types.Rule`, `types.Predicate`, and `types.Comparison`: the compiler sorts
  them (`ruleset["rules"].sort()`, `sorted(predicates)`). `attr.s` gives order by default;
  `attrs.define` does **not**. Annotate them as `@attr.s(slots=True, auto_attribs=True)` or
  `@define(order=True)`.
- With `auto_attribs`, an annotated class attribute becomes a field: annotate `_comparators` /
  `_operators` as `ClassVar[...]`.
- PEP 695 `type` aliases are not runtime classes: `isinstance(v, QualityValue)` raises. Validate
  with a module constant `QUALITY_TYPES = (int, float, str)` plus an explicit `bool` exclusion.
- `Story` holds a dict: declare `rulebook: CompiledRulebook = field(eq=False)` so `Story`
  equality/hash use `identity` only (hashing a frozen attrs instance with a dict field raises).
- Add `ravel.utils.*` to the strict override: `types.py` calls `evaluate_term`, whose unannotated
  `Any` return would trip `warn_return_any`.
- `Ruleset.locations` is `dict[str, object]` (non-`Situation` concepts store lists of strings via
  `_dummy_handler`); `Story.situation()` narrows with `isinstance(..., types.Situation)`.
- Engine value types use only engine-local names in annotations (no `TYPE_CHECKING`-only imports),
  so the 3.14 deferred-annotation caveat in CLAUDE.md never applies to them.

## Decided while you slept

| # | Decision | Why | Reversibility |
|---|---|---|---|
| 1 | New packages `ravel.engine` / `ravel.app` / `ravel.adapters`; `ravel.vm` deleted | Nothing survives; stale imports fail loudly | Moderate: rename is mechanical |
| 2 | Engine interprets existing directives; `GetChoice` is the YIELD point; no IR opcodes | Smallest change that satisfies FR-009; the §8.2 IR buys nothing yet | Easy: an IR can compile to the same frames later |
| 3 | Halt clears stack and offered; no exit events on halt | "No further directives" and a canonical halted save | Easy |
| 4 | Dead end = `Outcome(label="", dead_end=True)` | Spec wants a distinguishable flag, not a magic label | Easy |
| 5 | Story identity = `sha256:` of canonical JSON of rules+locations+givens + `IR_VERSION`; excludes positions and `about:` | Whitespace/metadata edits keep saves valid; any semantic edit refuses | Moderate: changes invalidate existing saves (none exist) |
| 6 | Save format v1 with `"format": "ravel-save"`; loader validates version → story → shape → locations → resumability, in that order | Most specific error first; tampered saves can't soft-lock | Easy before release |
| 7 | Saved `status: "running"` is refused | Snapshots are only taken at rest | Easy |
| 8 | `offered` must match what the engine re-derives from the saved state | Catches tampering and IR drift the hash missed | Easy |
| 9 | Non-finite floats and bools are rejected as quality values | JSON can't round-trip them; saves must be byte-stable | Easy |
| 10 | `- end:` needs no PEG change; outcome is the stripped inline text; a block value is a `ParseError`; no warning for directives after `end` | YAGNI, Principle V | Easy |
| 11 | blinker dropped entirely; colorclass kept | Nothing uses blinker; swapping colorclass is unrelated churn | Easy |
| 12 | Strict per-module mypy for new packages + `types.py`/`queries.py`; no `disallow_untyped_calls` | Catches D9-class bugs without annotating the whole compiler | Easy: config |
| 13 | Constitution amendment is MINOR v1.2.0, not MAJOR | Principles keep their rules; only enumerated surfaces change | Easy: bump label |
| 14 | Acceptance tests are plain pytest in `tests/acceptance/`; hypothesis `derandomize=True` | No Gherkin pipeline exists; CI must not flake | Easy |
| 15 | `GameSession` is the only mutable object; engine calls are pure | One obvious place for "current game"; a future web runner uses the engine directly | Moderate |
| 16 | CLI keeps `ravel.cli:main` entry point and module path | Console script and `TestMain` stay stable | Easy |
| 17 | syml from PyPI; git-tag source fallback, never path | Reproducible lock in CI | Easy |
| 18 | Menu numbering and `save`/`load`/`s`/`q`/`help` parsing live only in `ConsoleUI` | FR-026 thin adapter | Easy |
| 19 | (red team) Commit the whitespace-only working-copy re-indent of `examples/taxi/mail.ravel` in US1 | HEAD's copy fails under syml 1.0, so CI would fail the "every example loads" test | Easy: it is the same re-indent US1 applies elsewhere |
| 20 | (red team) `validate_resumable` checks every frame, not just the top; halted labels must be story `End` labels | A tampered lower frame could replay an intro or hit an unhandled directive | Easy |
| 21 | (red team) Saves capped at 1 MiB; strict UTF-8; NaN/Infinity/duplicate keys refused; every decode failure is a `LoadRefusedError` | SC-006: a bad `load` must never kill the live game | Easy |
| 22 | (red team) `save FILE` only overwrites empty files or existing ravel saves, default name included (narrows US5-AS3's "any existing file" to "any existing save") | `save pyproject.toml` would otherwise destroy a file | Easy: drop the guard |
| 23 | (red team) Int qualities bounded to signed 64-bit | Unbounded ints crash `json.dumps` past 4300 digits | Easy |
| 24 | (red team) Constraints, `value`, and `[Quality]` expression gaps stay unfixed and documented | Pre-existing, no example uses them, not in D1–D20 | Easy: one choke point + `IR_VERSION` bump |
| 25 | (red team) Save-sourced strings print via `repr()` in the CLI | Hostile saves cannot inject terminal control sequences | Easy |
| 26 | (deepen-plan-loop, decided while you slept) `contracts/cli.md`'s `save` row now reads `session.save(FILE or DEFAULT_SAVE_NAME)` instead of the literal `"ravel-save.json"` | `session-api.md` already names the constant `DEFAULT_SAVE_NAME: Final = "ravel-save.json"`; the CLI contract had drifted to a duplicated literal | Easy: rename only |
| 27 | (red team, iteration 2) Quality names and `str` values must be surrogate-free (UTF-8 encodable) | A JSON `\udc80` escape loads fine and then crashes the next `save` with `UnicodeEncodeError`; validation must guarantee that every valid state encodes | Easy: one check in `Qualities` |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Principle VI public-API break (vm events/signals/`send_input`, runners) | FR-005/007/034/037; the old surface embodies D1–D9 | Compatibility façade: re-creates D6–D8, keeps blinker, no callers (see above) |
| New dev dependency `hypothesis` | FR-032 property test over ≥200 playthroughs | Hand-rolled random loop: no shrinking, no reproducible counterexamples |
