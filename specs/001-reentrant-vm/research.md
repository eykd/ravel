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

---

## Planning Decisions (sp:03-plan)

Dated 2026-09-27, taken without the principal (asleep); each is summarised in plan.md's
"Decided while you slept". Brainstorm alternatives already rejected there (patching the VM,
`- halt:` / `- finish:` / reserved-quality endings, index-based saves) are not re-opened.

### PD-01. syml 1.0 source

- **Decision**: `syml>=1.0,<2` from PyPI; if `uv lock` cannot resolve 1.0.0 from the index, pin
  `[tool.uv.sources] syml = { git = "https://github.com/eykd/syml", tag = "v1.0.0" }`.
- **Rationale**: FR-001 needs a reproducible lock that CI can install; `../syml` is 1.0.0 locally.
- **Alternatives**: path source `../syml` (not reproducible in CI; rejected); vendoring (no).

### PD-02. Package layout

- **Decision**: new `ravel.engine` (domain), `ravel.app` (application), `ravel.adapters`
  (story source, save store); `ravel/cli.py` stays in place as the CLI adapter; `ravel/vm/` is
  deleted whole once the CLI switches.
- **Rationale**: no old VM code survives; a new name makes stale imports fail loudly and keeps
  the `ravel.cli:main` entry point stable.
- **Alternatives**: rewrite inside `ravel.vm` (ambiguous half-migrated state mid-branch);
  `ravel.domain` naming (collides conceptually with the compiler, which is also domain).

### PD-03. Choice blocks: interpret, don't generate IR

- **Decision**: the engine interprets today's compiled directives (`Text`, `Operation`,
  `BeginChoices`, `Choice`, `GetChoice`, new `End`). `BeginChoices` gathers the block and parks
  the frame's ip on `GetChoice` (the YIELD point). VM spec §4 opcodes, §6.2 rulebook JSON, and
  §8.2 codegen are marked deferred.
- **Rationale**: satisfies FR-009 with no compiler rewrite; ip positions remain stable per
  compilation (guarded by the identity hash).
- **Alternatives**: compile to explicit `DISPLAY_CHOICE`/`YIELD` instructions (more code, no
  behavior gain now; can be added later behind `IR_VERSION`).

### PD-04. Frame and choose semantics

- **Decision**: `Frame(location, ip)`, no `local_state`. `choose` on an in-situation menu sets
  the parent's ip to `GetChoice + 1` *before* pushing the child, so the gather runs after the
  child pops. End-of-directives pops unconditionally.
- **Rationale**: fixes D2/D3 structurally; saved frames need no "paused" flag.
- **Alternatives**: advance the parent ip on pop (needs a "returning from choice" marker).

### PD-05. Halt semantics and dead end

- **Decision**: `End` and dead ends clear the stack and `offered`, set `Outcome(label, dead_end)`,
  emit one `Halted`, and emit no `SituationExited`. Dead end = `Outcome("", dead_end=True)`.
- **Rationale**: one canonical halted state for saves; FR-018 "no further directives".
- **Alternatives**: keep frames for inspection (non-canonical saves); a magic `"dead-end"` label
  (collides with author labels).

### PD-06. Story identity

- **Decision**: `"sha256:" + sha256(canonical_json({"ir": IR_VERSION, "rulebook": …, "givens":
  …}))`; canonical encoder maps attrs instances to `{"type": ClassName, **fields}`, the
  `types.VALUE` sentinel to `{"type": "VALUE"}`, `str` subclasses (syml `Source`) to `str`.
  Excludes source positions and `about:` metadata.
- **Rationale**: whitespace, comment, and metadata edits keep saves valid; any edit that can
  move an ip or change semantics refuses the load (FR-022, FR-024).
- **Alternatives**: hash of source bytes (comment edits break saves); mtimes (non-deterministic);
  include metadata (title typo fixes would break saves).

### PD-07. Quality values

- **Decision**: `Qualities` is a frozen sorted tuple of pairs. Values must be `int` (not `bool`),
  finite `float`, or `str`; anything else raises `InvalidQualityValueError` at the operation.
  Unset qualities read as `None` in `QualityChanged.old` and as `0` in predicates/operations (as
  today).
- **Rationale**: immutable, hashable, canonical order for byte-identical saves; JSON can't
  round-trip NaN/inf and would coerce bools.
- **Alternatives**: `MappingProxyType` (not hashable, wraps a mutable dict); `frozendict` (not in
  3.14 stdlib; new dependency).

### PD-08. Save format v1 and decode order

- **Decision**: `{"format": "ravel-save", "format_version": 1, "story_id", "state": {qualities,
  stack, status, offered, outcome}}`, canonical JSON + `\n`, unknown keys refused. Decode checks:
  JSON → format tag → version → story id → shape → locations → resumability.
- **Rationale**: most useful error first; version before anything version-dependent.
- **Alternatives**: VM spec §6.3 layered schema (layers deferred); MessagePack (not
  human-readable).

### PD-09. Resting-state validation on load

- **Decision**: refuse `status: "running"`; refuse a waiting state whose `offered` differs from
  what the engine re-derives (query menu or the top frame's choice block); refuse top ip not on
  `GetChoice`.
- **Rationale**: a hand-edited or stale save can never soft-lock or crash the engine later.
- **Alternatives**: trust the file (a bad ip surfaces as an IndexError mid-game).

### PD-10. `end` compilation

- **Decision**: dispatch `end` in `compile_directive` (no PEG change); outcome = stripped inline
  text; a block value is a `ParseError`; no warning for directives after `end`.
- **Rationale**: Principle V; spec edge case "Directives after `end`: never run. No compile error."
- **Alternatives**: a grammar rule (unneeded); a lint warning (no warning channel exists).

### PD-11. Menu order

- **Decision**: keep `queries.query` order (predicate count desc, then location ID desc), document
  it in VM spec §7.3, pin it with a test.
- **Rationale**: spec says pin, don't redesign (D17); saves store IDs so order is presentation only.
- **Alternatives**: source order (a follow-up if David prefers).

### PD-12. blinker and colorclass

- **Decision**: drop `blinker` from `[project].dependencies`; keep `colorclass`.
- **Rationale**: nothing uses blinker after the rewrite (the CLI renders returned outputs);
  replacing colorclass with `click.style` is unrelated churn.
- **Alternatives**: per-session anonymous `Signal()` fan-out in the CLI (no consumer needs it).

### PD-13. Type checking

- **Decision**: per-module override for `ravel.engine.*`, `ravel.app.*`, `ravel.adapters.*`,
  `ravel.cli`, `ravel.types`, `ravel.queries`: `check_untyped_defs`, `disallow_untyped_defs`,
  `disallow_incomplete_defs`, `disallow_any_generics`, `warn_return_any`, `strict_equality`. Not
  `disallow_untyped_calls` (the compiler stays unannotated). Add `CompiledRulebook`/`Ruleset`
  TypedDicts; annotate `Environment.load`/`load_rulebook` returns. Remove `syml.*` from the
  `ignore_missing_imports` override.
- **Rationale**: FR-035; `check_untyped_defs` alone would have caught D9.
- **Alternatives**: global `strict = true` (drags the whole compiler into annotation work).

### PD-14. Engine shape: functions, not an executor class

- **Decision**: module functions `start`, `choose`, `present`, `validate_resumable` taking the
  `Story` explicitly; a private per-call `_Run` accumulates outputs. `GameSession` (app) is the
  only mutable holder.
- **Rationale**: FR-005's two operations; nothing to configure on an executor instance.
- **Alternatives**: VM spec §7.1 `VMExecutor(rulebook)` with `step`/`run_until_yield`/`resume`
  (public `step` would expose `RUNNING` states nobody needs).

### PD-15. Acceptance tests

- **Decision**: plain pytest end-to-end tests in `tests/acceptance/test_usNN_<slug>.py`, marked
  `acceptance`, docstrings naming spec scenarios (`US2-AS3`). The pytest-bdd/Gherkin pipeline in
  the plan template does not exist in ravel and is not added.
- **Rationale**: no new tooling; same outer-loop role.
- **Alternatives**: add pytest-bdd (new dependency and pipeline for six files).

### PD-16. Property test

- **Decision**: hypothesis (dev only). Strategy: `lists(integers(0, 10_000), max_size=40)` of
  choice indices taken modulo menu size, stop at halt; `split = integers(0, len(path))`. Settings
  `max_examples=200, deadline=None, derandomize=True`. Compare outputs after the split and
  `encode_save` of the final states.
- **Rationale**: FR-032/SC-003; derandomized for a flake-free CI.
- **Alternatives**: random module loop (no shrinking).

### PD-17. CLI mechanics

- **Decision**: `ConsoleUI(session, verbose, read_line=input, echo=click.echo)`; tests use
  `CliRunner` with `input=` and `monkeypatch.chdir(tmp_path)`; `--load` failure and unexpected
  errors exit 1; halt, `q`, EOF, Ctrl-C exit 0. `FileSaveStore` writes atomically (temp +
  `os.replace`).
- **Rationale**: FR-026–FR-030; injectable I/O keeps the UI unit-testable.
- **Alternatives**: `click.prompt` (reprompt behavior fights our command parsing).

### PD-18. Constitution amendment

- **Decision**: v1.1.0 → v1.2.0 (MINOR): VI's public surface list and VII's layer/file list are
  updated to the new packages; II notes the strict per-module set. Lands as its own
  `docs: amend constitution …` commit at the start of US2. Flagged for David's sign-off.
- **Rationale**: no principle is removed or redefined; only enumerations change (Versioning Policy).
- **Alternatives**: MAJOR bump as the spec guessed (overstates the change).

### PD-19. SC-009 baseline

- **Decision**: before bumping syml, dump `as_data()` of every example under 0.6.2 into the
  scratchpad; after re-indenting under 1.0, compare; record "identical" in the US1 commit body.
  Not a permanent test.
- **Rationale**: CI has no 0.6.2 (spec SC-009).

### PD-20. Fixture story

- **Decision**: `tests/fixtures/stories/mini/begin.ravel` with: `given: Count += 1` (once-only
  check), a `fork` situation (choice block + gather + effect), a choice whose body ends in
  `- end: escaped`, and a route that sets `Location = "Nowhere"` to reach a dead end.
- **Rationale**: FR-033; Cloak can't reach these.
