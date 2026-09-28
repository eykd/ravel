# Ravel diagnosis: syml 1.0 migration + VM/runner/event defects

Date: 2026-09-27. Scope: read-only. Repro scripts live next to this file in the scratchpad
(`play.py` scripted ConsoleRunner driver, `qr.py`/`qr2.py` QueueRunner drivers, `xtalk.py`
two-runner cross-talk, `mini/begin.ravel` minimal choice+gather story, `dump.py`/`fix.py`
syml 0.6.2 vs 1.0 comparison, `venv0/` = syml 0.6.2, `venv1/` = syml 1.0.0 editable,
`ravel-copy/` = throwaway copy of the repo).

**Environment caveat.** `uv.lock` pins syml **0.6.2**. During this session ravel's own `.venv`
was observed with syml **1.0.0** (editable from `../syml/src`) and later back on 0.6.2, so
something (the concurrent agent, or a `uv run` sync) is flipping it. With 1.0 installed, `ravel
run examples/cloak` fails at load; with 0.6.2 it plays. Beware: `uv run` re-syncs `.venv` to the
lock.

---

## 1. syml 0.6.2 -> 1.0.0 migration impact

### 1.1 Result in brief

- **One breaking change hits ravel: CHANGELOG item 17.** A valueless key inside a list item
  (`- when:`, `- choice:`, `- effect:`) now takes block content only if it is indented **past the
  key's own column**, not just past the `-`. Ravel's house style puts the child list at the key's
  column, which now raises `OutOfContextNodeError`:

  ```
  bar-dark.ravel:24:4: Line 24, at column 4, is a list item, but the open block at column 4
  holds keys; ... Hint: a list under a key must be indented past the key's column.
  ```
- **Every example file fails**: all 6 cloak files, 3 in `simple/`, and `taxi/begin.ravel`. Only
  `taxi/mail.ravel` parses (it's also dirty in git; I left it alone).
- **After re-indenting, it's safe.** `fix.py` adds two spaces under each `- key:` block. With
  that, `as_data()` under 1.0 is **byte-identical** to 0.6.2 for every example file. No other
  1.0 change alters any existing example.
- **Test suite under 1.0: 33 failed, 4 errors, 450 passed.** All 37 trace to item 17: through
  the cloak fixture, or through inline SYML strings in `test_compiler_rulebooks.py` and
  `test_queries.py`. After re-indenting the examples and 19 fixture lines, 1 failure remained. It
  was a deeper nested `- choice:` inside `TEST_RULEBOOK_SYML` (line ~19 of the string) that my
  regex missed; the cause is the same. Baseline under 0.6.2 is 487 passed.
- **mypy** on `src` with syml 1.0 installed is clean.

### 1.2 Call sites (`rg -n syml src tests`)

| Call site | 1.0 status | Action |
|---|---|---|
| `src/ravel/environments.py:66` `syml.parsers.parse(source, filename=name).as_source()` | Still supported (`parse` is now public API, `syml.parse`). `as_source()` is one of the two supported tree methods (item 16). | Optionally switch to `syml.parse(...)`. No behavioral change. |
| `src/ravel/types.py:4` `from syml.basetypes import Pos, Source` | Both exist. `Pos` coordinates now refer to the original text (item 10), so error positions get *more* accurate. | None. |
| `src/ravel/utils/strings.py:1,8` `Source.from_text(text, substring, **kwargs)` | Same signature `(text, substring=None, source_text=None, filename=None)`. It still uses `re.search(substring, text)`, so a substring with regex metacharacters is still a latent bug, as before. Now only `\n` counts as a line break. | None required. |
| `tests/test_compiler_rulebooks.py:4,91,105,120,136,154,181,371` `syml.loads(...)` | Works, but the inline documents use the old indentation. | Re-indent `- when:` / `- choice:` / `- effect:` children (~18 lines). |
| `tests/test_queries.py:4,66` `syml.loads(TEST_RULES)` | Same. | Re-indent 2 lines. |
| `tests/test_environment.py:45` (docstring only) | n/a | None. |
| `pyproject.toml` `syml>=0.6`; `uv.lock` 0.6.2 | Floor too low. | `syml>=1.0,<2`. Relock. |
| `pyproject.toml` `[[tool.mypy.overrides]] module=["syml.*"] ignore_missing_imports` | 1.0 ships `py.typed` (item 36). | Drop `syml.*` from the override. |

### 1.3 Semantic changes to watch (latent, none triggered by current files)

- **Item 1: absent value `None` -> `""`.** Two consequences:
  - `- effect:` with nothing under it now reaches `compile_effect("")`, a parse error. Before, it
    raised `ParseError("Unrecognized effect type")`.
  - An empty `when:` becomes `[""]` via `get_list_of_sources`, a comparison parse error.

  The error message changes either way.
- **Item 4: keys must match `[a-z][a-z0-9_-]*`.** Rule names like `Look:`, `lookAround:`, or
  `look.at:` silently become text at top level. In a mapping they raise. All current rule names
  are lowercase kebab. Quality names are only ever *values* (`"Wearing Cloak" = 1`), so they're
  unaffected. The language spec (§8.3 Location Names) should state the key rule.
- **Item 20: a blank line inside a value becomes `\n\n`.** `compiler/text.py:6` does
  `.replace("\n", " ")`, which turns that into a double space. `IntroTextParser` receives
  `unwrap(...)`, which also yields a double space. A proper paragraph-break rule is worth
  deciding.
- **Items 19/21: a deeper `key: value` line after an inline value joins that value's text.** An
  indented `#` is now text, not a comment. Cloak has no indented comments.
- **The language spec needs the same re-indent.** `docs/RAVEL_LANGUAGE_SPEC.md` shows the old
  layout at lines ~76, 277, 347, 452-493, 561, 625-631, and 704. Fix these alongside the examples.

---

## 2. Concrete VM / runner / event defects

Each defect is tagged by layer: **[R]** runner/CLI, **[V]** VM/state, **[E]** events/signals,
**[L]** language or story content. Transcripts come from `play.py`/`qr*.py` under syml 0.6.2.

### 2.1 The two most important root causes

**D1 [R]. Story begins twice in the CLI.** This is the #1 user-visible bug.
- `StatefulRunner.__enter__` calls `self.begin()` -> `vm.begin()` (`vm/runners.py:30`, 78-79).
- `ConsoleRunner.run` then calls `self.vm.run()` (`cli.py:130`), which calls `self.begin()`
  again (`vm/machines.py:67-68`).

The result is two `initialize_from_givens` calls and two `push(begin_state)`. It's the *same*
`Begin` instance twice, and each one spawns a `DisplayPossibleSituations`. Every opening choice
must be made twice, and the chosen situation is replayed:
```
-- INPUT #1  depth=3  stack=['Beg','Beg','Dis']      [1] Hurrying through the rainswept November night…
-- INPUT #2  depth=4  stack=['Beg','Beg','Dis','Dis'] [1] Hurrying through ... (same menu again)
   TEXT: Hurrying through ... / [1] Press onward!
   TEXT: You press onward ...
   TEXT: Hurrying through ...            <- intro replayed by the second DS
   [1] Press onward!                     <- must press onward twice
```
Givens using `+=` are applied twice. `mini/` has `given: Count += 1`, which gives `Count: 2` in
the CLI and `1` in QueueRunner. Separately, `cli.py:129-130` `while True: self.vm.run()` means
any drained queue re-begins on top of the live stack and re-applies givens over live qualities.
`tests/test_cli.py:19-25` (`scripted_input` docstring) already documents this: "or the console
runner's `while True` loop restarts the story forever."

**D2 [V]. `DisplaySituation.display()` does not stop at a choice point.**
- The class docstring (`machines.py:29-38`) says display runs "until we encounter a GetChoices
  or the end".
- The loop (`vm/states.py:75-88`) exits only on `paused` or `IndexError`.
- `handle_getchoice` (`states.py:109-111`) sends `waiting_for_input` and falls through to
  `self.index += 1`, continuing with the directives *after* the choice block.

This only looks correct in `ConsoleRunner` because its `handle_waiting_for_input` **blocks inside
`vm.send`** (`cli.py:65-86`). The player answers synchronously, `DisplaySituation.receive` calls
`vm.do_push` directly (`states.py:117-119`, bypassing the queue), and that pauses the parent in
the middle of its own loop. So the VM's semantics depend on whether the runner blocks inside an
event handler, which is the opposite of re-entrant. The `do_push` bypass is a workaround for D2,
not an independent design. Proof with `mini/begin.ravel` (text, choice L, choice R, gather text,
`effect: Place = "Middle"`):
```
QueueRunner (non-blocking):                 ConsoleRunner (blocking):
  TEXT You are at the start.                  TEXT You are at the start.  [1] Go left [2] Go right
  CHOICE go-left / CHOICE go-right            > 1  TEXT You go left.
  WAIT on DisplaySituation                         TEXT You are at the start.  (D1 replay)
  TEXT After the choice, the story continues. > 2  TEXT You go right.
  WAIT on DisplayPossibleSituations                TEXT After the choice, ... (x2, D1)
  Q {'Place': 'Middle'}   <- gather + effect ran BEFORE the player chose
  choose(0) -> TEXT You go left. -> 0 choices (dead end)
```
In QueueRunner the parent situation is popped *before* the choice is made. The chosen
sub-situation is then pushed by the wrong receiver (see D5).

### 2.2 Other defects

| # | Layer | Location | Defect / evidence |
|---|---|---|---|
| D3 | V | `states.py:82-83` | `if not vm.queue: vm.pop()`: whether a finished situation pops depends on unrelated pending queue work. Under D1 the finished `Press onward` frame is left on the stack (`depth=7`, `stack=[...,'Dis:Hurrying','Dis:Press onward','Dis:Hurrying']`). It unwinds only later, when a resume hits `IndexError` again, so exit events come out of order. `tests/test_vm_states.py:49-58` pins this ("must not pop itself"). |
| D4 | V/E | `machines.py:102-112`, `118-128` | Events fire *after* the transition's work. `enter_state` is sent after `state.enter()` has already emitted all display, choice, and wait events. `resume_state` comes after the redisplay. `pause_state` comes after `pause()`. The observed order is `TEXT…, WAIT, enter_state DisplaySituation, exit_state …`. `tests/test_runners.py:31-86` pins that order. |
| D5 | R/E | `runners.py:95-107`, `122-127` | QueueRunner merges menus from different states into `choice_events`, but `choose()` sends to the *last* waiter only. After `choose(0)` on the intro: `choice_events == ['begin::intro::press-onward', 'begin::intro']`, `waiter.state == DisplayPossibleSituations`. Choosing "press onward" routes it into DPS.receive, which works by accident because both receivers resolve a location name. `test_runners.py:101-114` pins the merged list. |
| D6 | E | `signals.py:26-43`, `runners.py:46-48` | Blinker **named, process-global** signals. `VirtualMachine.signals` is an instance, but its attributes are class-level shared signals. `xtalk.py`: with two runners, only A runs, yet B receives A's events: `B waiting: True`, `B.waiter belongs to A's VM: True`. `B.choose(0)` enqueues work on **A's** VM while B's stack stays `[]`. Handlers also leak if `__enter__` raises after `_setup_handlers()` (`runners.py:28-30`), because `__exit__` never runs. |
| D7 | E | `states.py:46`, `111`; `events.py:77-80` | `waiting_for_input.send_input` is a lambda closing over `vm` and `self`. It isn't serializable. A stale waiter can be called after its state was popped, and calling it twice double-pushes. Nothing guards against either. |
| D8 | E | `events.py:28-80` | Frozen events hold **live mutable `State`** objects. `display_text` emitted at directive 1 later shows `state.index == 5` (`qr.py`: `TEXT Hurrying... \| state.index now 5`). `test_runners.py:60-78` asserts `index=5` on every event of that step because of this. |
| D9 | E | `events.py:38-40`; `machines.py:107` | `pause_state.state: str`, but it receives a `State`. mypy passes only because function bodies are unchecked (`check_untyped_defs` off). `quality_changed` (`events.py:83-89`) annotates `initial_value`/`new_value: int`, but values are `None`/`str`/`float`. |
| D10 | V/E | `events.py:15-22`; `rg "events\.(begin\|end)\("` = no hits | **The game cannot end.** `begin`/`end` events exist but are never sent. There's no HALT, and `Begin`/DPS are never popped. `**You have won**` (`bar-light.ravel:29`) is plain text: after winning, `look-at-message` stays on the menu and can be re-read forever (INPUTs #15-#18). |
| D11 | V/R | `states.py:38-46`; `cli.py:65-81` | **A situation or query with zero choices soft-locks.** DPS still sends `waiting_for_input` with an empty menu. The CLI then loops `That's not an option.` / `I'm sorry, what?` until EOF or `q` (`mini/` tail). No "dead end" or "end of story" is signalled. |
| D12 | V | `states.py:43` vs `102` | Choice `index` semantics differ. DPS uses the menu ordinal (`enumerate`). DisplaySituation uses the **directive index** (`index=3` for the first inline choice). ConsoleRunner ignores both and counts itself (`cli.py:62-63`), and QueueRunner uses list position. |
| D13 | V | `machines.py:87-92` | `initialize_from_givens`: `state = self.qualities … self.qualities = state` is a no-op alias (the same dict). Givens mutate live qualities in place, so any re-begin (D1) overwrites play state. |
| D14 | R | `runners.py:37-44` | `StatefulRunner.__iter__` treats *any* `IndexError` raised during an action as "queue empty" and stops silently. The first one usually comes from the eager f-string `self.queue[0]` in `machines.py:59`. It masks real bugs. |
| D15 | R | `runners.py:81-93` vs `110-114` | `StatefulRunner` uses `self.text_events`/`self.all_events`, which only the `QueueRunner` subclass defines. `ConsoleRunner.choice_events` holds location strings, but `StatefulRunner.choose` expects events (`choice.choice`). This is a broken base-class contract. |
| D16 | R | `cli.py:58-59`; `events.py:54` | `sticky` (Ink-style `<>` glue, spec §9.1) is carried on `display_text`, but no runner honours it: every text is a separate wrapped paragraph. Cloak doesn't use `<>`. |
| D17 | V | `queries.py:56-63` | Menu order is `sorted((score, name, result), reverse=True)`, so ties break **reverse-alphabetically by rule name**, not by source order. The foyer menu shows `outside, foyer, cloakroom, bar`. It's deterministic but surprising, and save/replay by index depends on it. |
| D18 | V | `machines.py:17-52` | The VM mixes three concerns: the rulebook (immutable data), play state, and the I/O and scheduling machinery (`queue` of `functools.partial`, `signals`). None of the play state is addressable by name: frames hold compiled `Situation` objects rather than location IDs. |
| D19 | L | `examples/cloak/rooms.ravel` | Orphaned: nothing includes it, and its predicate `Foyer == 1` never holds. Dead content, and it also fails under syml 1.0. |
| D20 | L | `bar-dark.ravel`/`bar-light.ravel` | Story semantics, not engine. `Bar` is shared between the dark and lit bar, so after two dark looks the message is visible immediately on entering the lit bar. Both files declare `given: Fumbled = 0, Bar = 0` (applied twice, harmlessly). Untitled first texts (`bar-light::look`) show the same text as both menu label and body, which matches the spec's intro/tail rule. |

### 2.3 Route walkthrough (syml 0.6.2, `play.py`), apart from D1 at the start

- **Win.** The route: intro, press onward, cloakroom, look, look, the-hook, hang-up-cloak,
  leave, bar, look, look, look-at-message. The output is `TEXT: There seems to be some sort of
  message ... reads…` then `TEXT: **You have won**`, and the same menu is re-offered (D10).
  Qualities at win: `Wearing Cloak 0, Cloakroom 3, Bar 2, Fumbled 0`.
- **Lose.** The route: bar (cloaked), look-in-dark x2, fumble-around (`Fumbled 1`), leave,
  cloakroom (3 steps), hang, leave, bar. The lit bar immediately offers `look-at-scrambled-message`
  and shows `**Y… …ve …n**`. The game continues (D10).
- **Odd paths.** Foyer, outside, foyer, and back-and-forth all cycle correctly once past the
  intro. The stack returns to `['Beg','Beg','Dis','Dis']` (depth 4) after each top-level
  situation. The `Beg,Beg` / `Dis,Dis` duplication is D1, and the stale bottom DPS never gets a
  turn.
- **Takeaway.** Once past the intro, top-level storylet navigation (DPS -> push -> end -> pop ->
  resume DPS) is correct. The bugs concentrate in:
  - startup (D1);
  - in-situation choices and gathers (D2, D3, D5);
  - event ordering and identity (D4, D6-D9);
  - termination (D10, D11).

---

## 3. Save/load and re-entrancy requirements

### 3.1 What a faithful snapshot must contain

1. **`qualities`**: a `dict[str, int | float | str]`. Restore it verbatim. **Never re-run givens
   on load**: `+=` givens drift, as the `mini/` result shows. Givens belong to "new game" only.
2. **`stack`**: a list of frames `(location: str, ip: int)`, where location is the rule name
   (e.g. `begin::intro::press-onward`). Adopt the spec's "empty stack = query mode" model
   (`RAVEL_VM_SPEC.md` §7.3) instead of the `Begin`/`DisplayPossibleSituations` frames.
   Cloak's real depth is at most 2 (intro -> press-onward).
3. **Waiting context**: `status` (`running | waiting_input | halted`) plus the offered choices as
   **location IDs in display order**. Frame `ip` stays on the YIELD instruction (spec §4.5: YIELD
   does not advance the IP). Resuming validates the chosen location against the saved list.
4. **Rulebook identity**: a hash of the compiled rulebook, or of its source files plus the ravel
   version. The directive index is only meaningful against the same compilation, and
   `Environment` recompiles on mtime change (`environments.py:54-59`). Refuse, or warn, on a
   mismatch.
5. **Format version** for forward migration.
6. **Nothing else exists today.** There's no RNG (`rg random` finds nothing in `src`), and no
   visited/seen tracking or sticky-once flags. If they're added later (e.g. Ink-style "once-only"
   choices), they belong in the snapshot too: a `visits: dict[location, int]`, and an RNG
   seed/state if randomness ever appears.
7. **Pending, un-consumed output events: none.** The design must guarantee this by construction:
   output is produced by `step`/`resume` and returned, never stored.

### 3.2 What blocks serialization today

- The `queue` of `partial(bound_method, …)` (`machines.py:52-56`).
- The lambdas in `waiting_for_input` (D7).
- Blinker signal objects on the VM (`signals` field).
- Frames that hold compiled `Situation`/`Text`/`Source` objects plus a `paused` flag instead of
  a location ID.
- `begin_state` being a shared Factory instance.
- Implicit Python call-stack state from the synchronous `do_push` nesting inside a signal
  handler (D2): the "where we are" partly lives in suspended Python frames.

### 3.3 What "re-entrant" should mean here

- The core is driven from the outside, one call at a time: `start(rulebook) -> (state,
  outputs)`, `choose(rulebook, state, location) -> (state, outputs)`. Each call runs until the
  next YIELD or HALT and returns.
- There are no callbacks into the VM from event consumers. Output events are immutable **values**
  (text, choice list, quality change, halted), holding only strings and ints, with no `State`
  references and no callables.
- Every call is a pure function of `(rulebook, state, input)`. There are no module globals, so
  two sessions in one process can't interact. This fixes D6.
- Determinism is required: `load(save(s))` followed by the same choices must yield
  **byte-identical** output events and final state to continuing from `s`. That becomes a
  property test (Hypothesis over random choice sequences through Cloak) and an acceptance test
  (spec AT-INT-3).
- The runner blocking or not must not change semantics. This fixes D2: the gather runs only
  after `choose`.

---

## 4. Existing test inventory (under 0.6.2: 487 tests pass at 100% coverage)

**(a) Mechanical fixes for syml 1.0 only (indentation):**
- `tests/test_compiler_rulebooks.py`: ~18 lines of inline SYML, including the nested
  `- choice:` in `TEST_RULEBOOK_SYML`.
- `tests/test_queries.py`: 2 lines.
- Everything that loads `examples/cloak` via the `cloak_env` fixture (`tests/conftest.py:21-25`)
  is fixed by re-indenting the example files: `test_environment.py`, `test_cli.py`,
  `test_runners.py`, and `test_vm_machine.py` TestCloak/TestRun.

**(b) Pins behavior a rewrite should discard. These get replaced, not ported:**
- `tests/test_vm_states.py` (all). Pause/resume index semantics, the `if not vm.queue` pop
  (`:49-58`), `receive` using `do_push` (`:80-91`, docstring "without queuing"), and the `State`
  hook no-ops.
- `tests/test_vm_machine.py` (87 lines). push/pop/queue mechanics, givens via queue, and
  `TestRun` "drain the queue and stop".
- `tests/test_runners.py` (all, 138 lines). The exact event sequence, including `enter_state`
  trailing the displays, merged `choice_events`, the `index=5` live-state artifact, and handler
  bookkeeping.
- `tests/test_cli.py` TestConsoleRunner / TestConsoleRunnerVerbosity / TestRunCommand /
  TestGetInput. Keep the *intent*: quit on `q`, clean exit on EOF, reject bad input, verbose
  narration, and `--debug` pdb. The mechanics are tied to blocking signal handlers and
  `while True`.
- `TestMain` (log levels) and `TestHandleException` survive nearly as-is.

**(c) Untouched by a VM rewrite:**
- `test_grammars`, `test_parsers`, `test_comparisons`, `test_compiler_*` (except the fixture
  re-indent), `test_environment`, `test_loader`, `test_types`, `test_utils_text`,
  `test_exceptions`, and `test_queries` (the query semantics stay).

**Gap:** there's no end-to-end test that plays Cloak to a win or a loss, and none for
save/load. These are the acceptance tests to write first, from the transcripts in §2.3.

---

## 5. Recommended architecture sketch (Clean Architecture)

`docs/RAVEL_VM_SPEC.md` (untracked, "0.1 Draft") already *is* this target design:
`VMExecutor.step/run_until_yield/resume` (§7.1), frames of `(location, ip)` (§2.3), YIELD and
HALT (§4.5), and "empty stack = query mode" (§7.2-7.3). Build to it. Defer spec §3 (quality
layers `location/session/player/global`) and the HATEOAS mode: neither is needed to play, save,
load, and win.

**Domain (`ravel.vm.domain`: pure, no I/O, no blinker, frozen attrs or dataclasses):**
- `Frame(location: str, ip: int)`.
- `GameState(qualities: Mapping[str, Quality], stack: tuple[Frame, ...], status: Status,
  offered: tuple[str, ...], rulebook_id: str)`.
- `Output` event values:
  - `TextShown(text, sticky)`
  - `ChoicesOffered(tuple[ChoiceView(location, label)])`
  - `QualityChanged(name, old, new)`
  - `SituationEntered/Exited(location)`
  - `Halted(reason)`
  - `DeadEnd()`
- `Engine(rulebook)` with `start() -> Step`, `choose(state, location) -> Step`, where
  `Step = (GameState, tuple[Output, ...])`. The engine runs until YIELD, HALT, or dead end.
  - At the end of a situation it pops implicitly.
  - With an empty stack it queries, making menu order an explicit, documented sort (fix D17 or
    pin it).
  - With zero matches it emits `DeadEnd`/`Halted`, never an empty wait (D11).
- Compile `Choice`/`BeginChoices`/`GetChoice` into explicit instructions (`DISPLAY_CHOICE`,
  `YIELD`), so the IP stops at YIELD (D2).
- Language addition for winning: a directive, or an effect on a reserved quality (e.g.
  `- end: You have won`), compiling to HALT (D10). Fix `bar-light.ravel` to use it. This is a
  language change, so bring it to David.

**Application (`ravel.app`):**
- `GameSession` use cases: `new_game`, `choose(index | location)`, `save() -> Snapshot`,
  `load(Snapshot)`, `current_choices`.
- Ports (Protocols): `RulebookSource` (compiled rulebook plus id/hash), `SnapshotStore`
  (save/load bytes), `OutputSink` (optional; the session can just return outputs).
- Snapshot codec: `GameState <-> dict` with a format version and the rulebook hash.

**Adapters:**
- The existing `Environment`/`Loader` become the `RulebookSource` adapter, adding a content hash.
- `JsonSnapshotStore` (file).
- The CLI: a plain loop — render outputs -> prompt -> `session.choose` — with `s`/`q` plus new
  `save <file>` / `load <file>` commands. It honours `sticky` glue (D16) and exits on `Halted`.
- Blinker, if kept at all, becomes an adapter that fans out returned outputs. Use per-session
  anonymous `Signal()` instances, never named globals (D6).

**Typing:** new packages are fully annotated (`Frame`, `GameState`, `Output` unions,
`Quality = int | float | str`). Turn on `check_untyped_defs` (at least per-module for
`ravel.vm.*` / `ravel.app.*` via `[[tool.mypy.overrides]]`); that alone would have flagged D9.
Also:
- Annotate `types.py` value objects: `Text`, `Operation`, `Comparison`, `Situation`, `Rule`.
- Type the compiled rulebook shape, which is currently `dict` of
  `{"rules": [...], "locations": {...}}`, as a `TypedDict` or small class.
- Drop `syml.*` from the mypy `ignore_missing_imports` override once on 1.0.

**Suggested order:**
1. syml 1.0 plus the re-indent of examples, tests, and spec. This is mechanical and green by
   itself.
2. Acceptance tests from §2.3: win, lose, save-mid-intro/load/continue.
3. Domain engine behind those tests.
4. Session and JSON store.
5. New CLI adapter.
6. Delete `vm/machines.py`, `states.py`, `runners.py`, `signals.py`, and their tests.
