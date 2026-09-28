# Feature Specification: Re-entrant VM with Save/Load and a Winnable Cloak of Darkness

**Feature Branch**: `001-reentrant-vm`
**Created**: 2026-09-27
**Status**: Draft
**Beads Epic**: `ravel-8qa`
**Beads Phase Tasks**: plan `ravel-8qa.1` · red-team `ravel-8qa.2` · tasks `ravel-8qa.3` · analyze `ravel-8qa.4` · implement `ravel-8qa.5` · harden `ravel-8qa.6`
**Brainstorm**: specs/brainstorms/2026-09-27-reentrant-vm-requirements.md
**Diagnosis**: [research.md](./research.md) (defects D1 to D20, cited below)
**Input**: User description:

> Let's upgrade to syml 1.0, then get the ravel.vm to a full re-entrant architecture that will
> let one play @examples/cloak/, save state, load state, and win the game. We can already play
> Cloak of Darkness through the CLI runner, but it's buggy. I'd like you to take a hard look at
> the VM, strip it down to bare studs if necessary, and get it working reliably. I don't know if
> the problem is in the VM itself or in the runner, or in the events themselves. It may help to
> solidify the typing annotations. You have permission to rearchitect anything necessary,
> upgrade pythons, libraries, etc. Please stick to a Clean Architecture style. You should end
> with as good test coverage, documentation, typing, etc. as when you started (or better). I'm
> heading to bed, so do what you can to make this thing work reliably.

**Implementation-detail note.** This feature is inherently architectural. The principal asked
for a Clean Architecture rearchitecture and for save/load. So the layer boundaries and the
save-file fields are part of *what* is being built, and this spec states them. Class names,
module names, and algorithms are left to planning.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Stories load under syml 1.0 (Priority: P1, hard prerequisite)

As a story author, I can load every example story and run the full test suite on syml 1.0, with
no change to what any story means.

**Why this priority**: Nothing else can be tested until the stories load. syml 1.0's
indentation rule (CHANGELOG item 17) breaks every example file and 37 tests (diagnosis §1.1).

**Independent Test**: Upgrade the dependency and re-indent the examples, inline fixtures, and
spec examples. Then run the whole suite, and compare each example's parsed data with its syml
0.6.2 parse.

**Acceptance Scenarios**:

1. **Given** syml 1.0 is installed, **When** each example story under `examples/` is loaded,
   **Then** it loads without a parse error, and its parsed data equals the syml 0.6.2 parse of
   the original file.
2. **Given** the upgraded dependency, **When** the full suite runs, **Then** every test passes at
   100% branch coverage, and ruff, mypy, and pre-commit are clean. This holds before any engine
   work starts.
3. **Given** syml 1.0 ships its own type information, **When** mypy runs, **Then** it passes
   without the override that ignored missing syml types.

---

### User Story 2 - A pure, re-entrant engine plays storylets correctly (Priority: P1)

As an engine user (a runner, a test, or a future web front end), I start a game and make
choices one call at a time. Each call returns the new game state plus a list of plain-value
outputs. The engine never calls back into my code, and never keeps state of its own between
calls.

**Why this priority**: This fixes the root causes: the double begin (D1), a situation that
doesn't stop at a choice (D2), the queue-dependent pop (D3), the global signals (D6), and events
that hold live state and callables (D7, D8). Save/load (US4) is impossible without it.

**Independent Test**: Drive the engine directly, with no CLI, through Cloak and through a
minimal fixture story. Assert on the returned states and outputs.

**Acceptance Scenarios**:

1. **Given** the Cloak story, **When** a new game starts, **Then**:
   - the outputs offer exactly one choice, `begin::intro`, with its intro label;
   - the status is waiting for input;
   - the qualities hold the givens (`Location = "Intro"`, `"Wearing Cloak" = 1`);
   - each given has been applied exactly once.
2. **Given** the intro menu, **When** the player chooses `begin::intro`, **Then**:
   - the intro's tail text is shown once;
   - the engine stops at the intro's choice block and offers only
     `begin::intro::press-onward`;
   - nothing after the choice block has run.
3. **Given** a fixture situation with text, a choice block, and then gather text followed by an
   effect, **When** the situation is entered, **Then** the engine stops at the choice block. The
   gather text has not been shown and the effect has not been applied. **When** a choice is then
   made, **Then** the output comes in this order:
   1. the chosen sub-situation's text;
   2. the sub-situation's exit;
   3. the gather text;
   4. the effect's quality change.
4. **Given** a situation that has run past its last directive, **When** the engine continues,
   **Then** that situation's frame is popped, and it always pops, whatever else is pending. With
   the stack empty, the engine queries and offers the matching situations.
5. **Given** qualities under which several situations match, **When** the engine queries,
   **Then** the menu is ordered by predicate count (highest first), then by location name
   (descending). The same state always produces the same menu.
6. **Given** a fixture story whose qualities match no situation, **When** the engine queries,
   **Then** it halts with the dead-end outcome and offers no menu.
7. **Given** two games running in the same process, **When** each makes choices, **Then**
   neither game's state or outputs are affected by the other.
8. **Given** any output the engine returns, **When** it is inspected, **Then** it contains only
   plain data (text, numbers, flags, location IDs). It holds no reference to engine state and no
   callable, and later calls never change it.

---

### User Story 3 - A story can end (Priority: P1)

As a story author, I write `- end: won` (or a bare `- end:`) as a directive, and when play
reaches it the game is over. As a player, winning or losing Cloak of Darkness actually ends the
game.

**Why this priority**: Without it, the principal's goal ("win the game") can't be observed:
after winning, the menu is offered again forever (D10).

**Independent Test**: Compile a fixture situation that uses `- end:` and run it through the
engine. Separately, play Cloak's win and loss routes and check that each halts with the right
outcome.

**Acceptance Scenarios**:

1. **Given** a situation containing `- end: won`, **When** the engine reaches that directive,
   **Then**:
   - the game halts immediately;
   - the halted output carries the outcome `won`;
   - no further directives run, whatever the stack depth;
   - no menu is offered.
2. **Given** `- end:` with no label, **When** it is reached, **Then** the game halts with an
   empty outcome.
3. **Given** `- end:` inside a choice's body, **When** that choice is made, **Then** the game
   halts from inside the sub-situation.
4. **Given** Cloak, **When** the player reads the intact message in the lit bar, **Then** the
   text `**You have won**` is shown and the game halts with outcome `won`.
5. **Given** Cloak, **When** the player reads the scrambled message, **Then** the scrambled text
   is shown and the game halts with outcome `lost`.
6. **Given** the language spec, **When** an author reads it, **Then** the `end` directive is
   documented in the directives section, the YAML structure summary, and the execution model.

---

### User Story 4 - Save and load a game (Priority: P2)

As a player, I save a game in progress to a file and later load it, even in a new process, and
continue exactly where I left off.

**Why this priority**: It's the second half of the principal's goal. It depends on US2's pure
state being serializable.

**Independent Test**: Through the session use cases with no CLI: play partway, save, load into a
fresh session, and continue. Compare the result with an uninterrupted run.

**Acceptance Scenarios**:

1. **Given** a game waiting at a menu, **When** it is saved, **Then** the file is JSON in a
   canonical form. It holds:
   - the format version;
   - the story identity;
   - the qualities, with their exact int, float, or string types;
   - the frame stack (location and position);
   - the status and outcome;
   - the offered choices as location IDs.
2. **Given** that save file, **When** it is loaded against the same story, **Then**:
   - the restored state equals the saved state;
   - no given is re-applied (a `+=` given is not applied a second time);
   - the pending menu is re-presented with the same labels, in the same order, as before the
     save.
3. **Given** a save made mid-game, **When** it is loaded and the same choices are made as in an
   uninterrupted run, **Then** every subsequent output is identical and the final state is
   equal. Saving both final states gives byte-identical files.
4. **Given** a save made against a story that has since been edited so that its compiled form
   differs, **When** it is loaded, **Then** the load is refused with an error saying the story
   has changed, and no game state is changed.
5. **Given** a file that isn't valid JSON, is missing fields, has an unsupported format version,
   or names locations the story doesn't have, **When** it is loaded, **Then** the load is refused
   with an error naming the problem, and no game state is changed.
6. **Given** a save of a halted game, **When** it is loaded, **Then** the game is halted with the
   same outcome, and no choice is accepted.

---

### User Story 5 - Play, save, and load from the command line (Priority: P2)

As a player at a terminal, I run `ravel run examples/cloak`, see the text and a numbered menu,
pick by number, and can type `save` or `load` at the prompt. I can also start from a save with
`--load`. When the game ends, the CLI tells me the outcome and exits.

**Why this priority**: The terminal is how the principal will verify the result by hand. The CLI
must be a thin adapter so its behaviour can't change engine semantics (D2).

**Independent Test**: Run the CLI with scripted input and captured output. Assert on the
transcript, the save files, and the exit codes.

**Acceptance Scenarios**:

1. **Given** `ravel run examples/cloak`, **When** it starts, **Then** the intro menu is shown
   once, and the opening choice is never asked twice (D1).
2. **Given** a menu, **When** the player types a valid number, **Then** that choice is made. Any
   other input that isn't a command is rejected with a message, and the prompt repeats.
3. **Given** a menu, **When** the player types `save` or `save FILE`, **Then** a snapshot is
   written (by default to `ravel-save.json` in the current directory, overwriting any existing
   file), its path is printed, and the same menu is still waiting.
4. **Given** a menu, **When** the player types `load` or `load FILE` with a valid save, **Then**
   the current game is replaced and the save's pending menu is shown. **When** the load is
   refused, **Then** the error is printed and the current game carries on untouched.
5. **Given** `ravel run examples/cloak --load FILE` with a valid save, **When** it starts,
   **Then** play resumes at the saved menu without any given being re-applied. **When** the
   save is corrupt or belongs to a different or changed story, **Then** the error is printed
   and the command exits non-zero.
6. **Given** play reaches an `end` directive, **When** the game halts, **Then** the CLI prints
   an end-of-game line that includes the outcome, and exits with status 0 without prompting
   again. A dead end also ends the run, with its own message.
7. **Given** the prompt, **When** the player types `q`, sends EOF, or presses Ctrl-C, **Then**
   the CLI exits cleanly with status 0. Typing `s` shows the qualities. Typing `help` or `?`
   lists the commands.
8. **Given** `--verbose`, **When** playing, **Then** quality changes and situation entry and
   exit are narrated. **Given** `--debug`, **When** an unexpected error occurs, **Then** the
   post-mortem debugger opens.

---

### User Story 6 - Prove it end to end (Priority: P3)

As the maintainer, I have automated proof that Cloak can be won, can be lost, and survives
save/load at any point.

**Why this priority**: It locks in the outcome against regression. It depends on US2 through
US4, and US5 for the CLI transcript test.

**Independent Test**: Run the end-to-end and property tests on their own.

**Acceptance Scenarios**:

1. **Given** Cloak, **When** a scripted player follows the win route, **Then** the game halts
   with outcome `won`. The route is: intro → press onward → cloakroom → look → look → the-hook
   → hang-up-cloak → leave → bar → look → look → look-at-message. The script selects by
   location ID, never by menu position.
2. **Given** Cloak, **When** a scripted player follows the loss route, **Then** the game halts
   with outcome `lost`. The route is: intro → press onward → bar (still cloaked) →
   look-in-dark → look-in-dark → fumble-around → leave → cloakroom → look → look → the-hook →
   hang-up-cloak → leave → bar → look-at-scrambled-message.
3. **Given** random playthroughs of Cloak, **When** each is split at a random point, saved,
   loaded into a fresh session, and continued with the same choices, **Then** the continued
   outputs and final state match the uninterrupted run for every generated example (at least
   200). For each generated playthrough:
   - each choice is taken as an index modulo the current menu size;
   - the sequence stops at halt;
   - the split point is anywhere from the start to the end.
4. **Given** the CLI with scripted input, **When** the win route is played with a `save`
   partway, then quit, then restarted with `--load`, **Then** the transcript ends with the win
   outcome.

---

### Edge Cases

- **Corrupt save** (not JSON, truncated, wrong types, missing fields): refused with a message
  that names the problem. The live game is untouched, and a CLI `--load` exits non-zero.
- **Story changed since save** (the compiled identity differs): refused with a "story has
  changed" error. Instruction positions are only meaningful against the same compilation.
- **Save from a newer or unknown format version**: refused with the version named.
- **Save naming a location the story lacks** (in the stack or in the offered choices): refused.
- **Choosing a location that isn't offered**: rejected with an error. The state is unchanged,
  and the same menu is still waiting.
- **Choosing after the game has halted**: rejected with a "game is over" error. The state is
  unchanged.
- **Choosing while not waiting for input** (a state that is running): rejected.
- **Dead-end menus** (a query that matches no situation): the game halts with the dead-end
  outcome. There is never an empty menu and never a soft lock (D11).
- **A `+=` given**: applied exactly once at a new game, and never on load (D1, D13).
- **Story files edited during a CLI session**: the session keeps playing its already-compiled
  story. A later `load` checks the save against the story as it was compiled at startup.
- **Directives after `end`**: never run. There's no compile error.
- **Two sessions in one process**: fully isolated (D6).

## Requirements _(mandatory)_

### Functional Requirements

**Dependency upgrade (US1)**

- **FR-001**: Ravel MUST depend on syml 1.0 or later and below 2.0, with a reproducible lock.
- **FR-002**: Every example story, inline test fixture, and language-spec example MUST be
  re-indented per syml CHANGELOG item 17, so that each example's parsed data equals its syml
  0.6.2 parse.
- **FR-003**: The type-checker configuration MUST stop ignoring missing syml type information.
- **FR-004**: The existing suite MUST pass at 100% branch coverage on syml 1.0 before engine work
  begins.

**Engine (US2)**

- **FR-005**: The engine MUST offer exactly two operations:
  - "start a new game" takes a compiled story;
  - "choose" takes a compiled story, a game state, and a location ID.

  Each MUST return a new game state and an ordered sequence of outputs, and MUST NOT call
  outward or keep state between calls.
- **FR-006**: Game state MUST be immutable. It holds the qualities, a stack of frames (location
  ID plus instruction position), a status (running, waiting for input, or halted), the offered
  choices (location IDs in display order), and the halt outcome.
- **FR-007**: Outputs MUST be immutable values holding only plain data. The kinds are:
  - text shown, with its glue flag;
  - choices offered, as location and label pairs in order;
  - quality changed, with the name, old value, and new value;
  - situation entered and situation exited, with the location;
  - halted, with the outcome and whether it was a dead end.
- **FR-008**: Each call MUST run until the game next waits for input or halts, and then return.
- **FR-009**: When a situation reaches a choice block, the engine MUST offer those choices and
  wait. Directives after the block MUST run only after the chosen sub-situation has finished.
- **FR-010**: When a frame runs past its last directive, the engine MUST pop it, unconditionally.
- **FR-011**: With an empty stack, the engine MUST query the story and offer every matching
  situation. The order is predicate count descending, then location name descending, and this
  order MUST be documented in the VM spec and pinned by a test.
- **FR-012**: A query with no matches MUST halt the game with a dead-end outcome. The engine
  MUST NOT offer an empty menu.
- **FR-013**: Choosing a situation from a query menu MUST enter it and show its tail text.
  Choosing an in-situation choice MUST enter that choice's sub-situation.
- **FR-014**: Givens MUST be applied exactly once, when a new game starts.
- **FR-015**: The engine MUST reject:
  - a choice of a location that isn't currently offered;
  - any choice while the game is halted;
  - any choice while the game isn't waiting for input.

  Each rejection MUST raise a clear error and leave the given state unchanged.
- **FR-016**: The engine MUST hold no module-level mutable state, so separate games in one
  process are fully isolated.

**Ending (US3)**

- **FR-017**: The language MUST accept an `end` directive with an optional inline outcome label
  (`- end: won`, or bare `- end:`). It MUST be accepted anywhere a directive may appear,
  including inside a choice body.
- **FR-018**: Reaching `end` MUST halt the game at once, at any stack depth. The halted output
  MUST carry the label verbatim (an empty label when bare), and no further directives or menus
  may follow.
- **FR-019**: Cloak of Darkness MUST end with outcome `won` after the intact message, and with
  outcome `lost` after the scrambled message.
- **FR-020**: The language spec MUST document `end` in the Directives section, the YAML
  structure summary, and the Execution Model.

**Save and load (US4)**

- **FR-021**: The application MUST provide session use cases for new game, choose, save, and
  load, over ports for the story source and the save store.
- **FR-022**: A save MUST be JSON in a canonical form (sorted keys, fixed separators) and MUST
  contain:
  - a format version;
  - the story identity, derived from the compiled story rather than file paths or timestamps;
  - the qualities, preserving int, float, and string types;
  - the frame stack;
  - the status and outcome;
  - the offered choices as location IDs.
- **FR-023**: Loading MUST restore the saved state exactly, MUST NOT re-apply givens, and MUST
  re-present the pending menu, with labels re-derived from the saved location IDs.
- **FR-024**: Loading MUST be refused with a specific error when:
  - the story identity differs;
  - the data is malformed or missing fields;
  - the format version is unsupported;
  - a saved location doesn't exist in the story.

  A refused load MUST leave no partially loaded state.
- **FR-025**: For any sequence of choices, save-then-load-then-continue MUST produce outputs
  identical to continuing uninterrupted, and a final state that saves to byte-identical data.

**CLI (US5)**

- **FR-026**: The CLI MUST be a thin adapter over the session use cases. It renders outputs, maps
  a menu number to a location ID, and ends its loop when the game halts.
- **FR-027**: The prompt MUST support:
  - a number, to choose;
  - `save [FILE]` and `load [FILE]` (default file `ravel-save.json` in the current directory);
  - `s`, to show qualities;
  - `q`, to quit;
  - `help` or `?`.

  Any other input MUST be rejected and the prompt repeated.
- **FR-028**: `ravel run DIR` MUST accept `--load FILE` to resume from a save checked against the
  story in `DIR`. A failed load MUST exit non-zero with the error.
- **FR-029**: On halt, the CLI MUST print an end-of-game line with the outcome (or a dead-end
  message) and exit with status 0.
- **FR-030**: The CLI MUST keep these behaviours:
  - `q` quits;
  - EOF and Ctrl-C exit cleanly;
  - bad input is rejected;
  - `--verbose` narrates quality changes and situation entry and exit;
  - `--debug` opens the post-mortem debugger on an unexpected error;
  - the log-level flags work.

**Verification (US6)**

- **FR-031**: End-to-end tests MUST play Cloak to `won` and to `lost` through the session,
  selecting by location ID. A CLI transcript test MUST cover win-with-save-and-reload.
- **FR-032**: A property-based test MUST check FR-025 over at least 200 generated Cloak
  playthroughs. Hypothesis is added as a development dependency only.
- **FR-033**: A minimal fixture story MUST exist for the behaviours Cloak can't reach:
  - a gather after a choice (FR-009);
  - a dead end (FR-012);
  - a `+=` given applied once (FR-014);
  - an `end` inside a choice body (FR-017).

**Architecture, quality gates, and docs**

- **FR-034**: The code MUST be layered:
  - **domain:** engine, game state, and outputs;
  - **application:** session use cases and ports;
  - **adapters:** the CLI, the JSON save store, and the file-system story loader.

  The domain MUST NOT import from the application or adapter layers, from I/O, or from blinker.
- **FR-035**: The new and rewritten packages MUST be fully annotated and type-checked with
  `check_untyped_defs` or stricter. The project MUST keep 100% branch coverage and clean ruff,
  mypy, and pre-commit runs.
- **FR-036**: Tests that pin the old buggy behaviour MAY be deleted or replaced. These are
  `test_vm_states.py`, `test_vm_machine.py`, `test_runners.py`, and the runner parts of
  `test_cli.py`. Compiler, grammar, parser, comparison, environment, loader, types, and query
  tests MUST be kept.
- **FR-037**: The old VM machinery (the machine, states, runners, and signals) MUST be removed
  once nothing depends on it.
- **FR-038**: Documentation MUST be updated:
  - the `CLAUDE.md` architecture section;
  - `docs/RAVEL_VM_SPEC.md`, marking implemented versus deferred sections and stating the
    menu-order rule;
  - `docs/RAVEL_LANGUAGE_SPEC.md`, for the `end` directive and the re-indented examples;
  - `README.rst`, for running, saving, and loading.
- **FR-039**: `examples/cloak/rooms.ravel` MUST be deleted.

### Key Entities

- **Compiled story (rulebook)**: The immutable result of compiling a story directory. It holds
  the situations keyed by location ID, their predicates and directives, and the givens. It has
  an **identity**: a stable fingerprint of its compiled content.
- **Location ID**: A situation's unique name, such as `begin::intro::press-onward`. It's used in
  frames, menus, choices, and saves.
- **Frame**: One entry on the stack. It is a location ID plus the position of the next directive
  to run in that situation.
- **Game state**: The qualities, the frame stack, the status (running, waiting for input, or
  halted), the offered choices, and the outcome. It is immutable, and it is everything needed to
  resume.
- **Output**: A plain value describing something the player should see or that happened: text,
  a menu, a quality change, situation entry or exit, or a halt.
- **Outcome**: The label attached to a halt. It is either the author's `end` label or the
  dead-end marker.
- **Save file (snapshot)**: The canonical JSON form of a game state, plus the format version and
  story identity.
- **Session**: The application-level use cases (new game, choose, save, load) that tie a compiled
  story, a game state, and a save store together.

## Success Criteria _(mandatory)_

### Measurable Outcomes

User-facing outcomes:

- **SC-001**: A scripted Cloak playthrough of the 12-choice win route ends with the text
  `**You have won**` and a halt with outcome `won`. No further menu is offered in 100% of runs.
- **SC-002**: A scripted Cloak playthrough of the loss route ends with the scrambled message and
  a halt with outcome `lost`.
- **SC-003**: Across at least 200 generated playthroughs with a random save point, a game resumed
  from a save produces identical subsequent outputs and a byte-identical final save, in 100% of
  cases.
- **SC-004**: No choice is ever presented twice in a row because of a startup replay. The opening
  choice is asked exactly once per new game (D1).
- **SC-005**: A player can start Cloak at the terminal, save, quit, restart with the save, and
  win, with no given re-applied and no state lost.
- **SC-006**: 100% of refused loads (a changed story, corruption, an unknown version, or an
  unknown location) print an error naming the cause and leave the current game playable.

Engineering gates (these are included on purpose, because the principal's request makes coverage,
typing, and architecture explicit deliverables):

- **SC-007**: Branch coverage is 100%. The ruff check, ruff format check, mypy (with
  `check_untyped_defs` or stricter on the new packages), and pre-commit all pass.
- **SC-008**: No module under the domain layer imports blinker, the CLI, or file I/O. A test
  checks this.
- **SC-009**: Every example story loads under syml 1.0 with parsed data identical to its 0.6.2
  parse. This is a one-time check during the migration, not a permanent test: CI has no 0.6.2.
  It's done by comparing against 0.6.2 parses captured before the upgrade.

## Assumptions

- syml 1.0 is installable reproducibly, from the index or a pinned source. Planning confirms
  which.
- Python 3.14 stays the floor. No interpreter change is needed.
- The story identity is derived from compiled content. Whether source positions are excluded (so
  whitespace-only edits keep saves valid) is decided in planning.
- Choice blocks carry no predicates today, so an in-situation menu is never empty. Only query
  menus can dead-end.
- Whether choice blocks compile to explicit VM-spec instructions (§8.2) or are interpreted with
  a yield point is decided in planning. Either satisfies FR-009.
- Whether blinker survives anywhere (for example as a CLI-only fan-out) is decided in planning.
  If nothing uses it, it's dropped from the runtime dependencies.
- **Constitution amendment (MAJOR), for the plan's Constitution Check.** Principle VII mandates
  that the VM expose frozen attrs events over blinker signals. Principle VI lists
  `vm/events.py`, `vm/signals.py`, and `send_input` as public API. FR-005, FR-007, FR-034, and
  FR-037 deliberately break both. The plan must list the break and amend VII (layering) and VI
  (the new public surface: session use cases, output values, and the save format), with the
  principal's sign-off.
- Deferred and out of scope:
  - quality layers (VM spec §3);
  - HATEOAS mode (§7.5);
  - rendering of `<>` glue (the flag is still carried);
  - visit counts, once-only choices, and RNG;
  - conditional `end`;
  - Cloak semantics beyond the two `end` directives (D20);
  - the latent syml 1.0 semantics that no current file triggers (diagnosis §1.3).

## Clarifications

### Session 2026-09-27

No live interview took place: the principal was asleep. The answers below are decisions taken
from his request and the diagnosis, and they stand in for the interview.

- Q: What order do the stories go in, and are any of them prerequisites? → A: US1 (syml 1.0),
  then US2 (engine), US3 (`end`), US4 (save/load), US5 (CLI), and US6 (end-to-end). US1 is a hard
  prerequisite: the suite must be green on 1.0 before engine work.
- Q: Can the existing VM tests be deleted? → A: Yes for `test_vm_states.py`,
  `test_vm_machine.py`, `test_runners.py`, and the runner parts of `test_cli.py`, which pin
  D1 to D8. Compiler, grammar, parser, and query tests are kept.
- Q: What is out of scope? → A: Quality layers, HATEOAS, glue rendering, visit counts, and RNG.
  Menu tie order (D17) is documented and pinned, not redesigned.
- Q: Does blinker stay? → A: Not in the core. The CLI's use of it is a planning detail.
- Q: What architecture? → A: Clean Architecture: domain, application, and adapters, with the
  domain depending on nothing outward.
- Q: How strict should typing be? → A: Full annotations and `check_untyped_defs` or stricter on
  the new packages, with 100% branch coverage.
- Q: Which docs change? → A: CLAUDE.md, both specs, and the README.
- Q: What happens to `rooms.ravel`? → A: It's deleted (D19).
- Q: What syntax does the end directive use? → A: `- end: <outcome>`, with the outcome optional.
- Q: What is the CLI save/load UX? → A: `save [FILE]` / `load [FILE]` at the prompt (default
  `ravel-save.json`), plus `ravel run DIR --load FILE`.

## Decided while you slept

| # | Decision | Why (one line) | Reversibility |
|---|---|---|---|
| 1 | Story order US1→US6, with US1 a hard prerequisite | Nothing loads under syml 1.0 until the re-indent lands | Easy: sequencing only |
| 2 | Buggy-behaviour tests may be replaced, and compiler, grammar, parser, and query tests are kept | Porting tests that assert D1–D8 would preserve the bugs | Moderate: they're in git history, but they test deleted code |
| 3 | Quality layers, HATEOAS, glue rendering, visits, and RNG are deferred, and D17 is only pinned | None is needed to play, save, load, and win | Easy: each is additive later |
| 4 | Blinker is out of the core | Global named signals caused D6, and callbacks caused D2 | Easy in the CLI, and deliberately hard in the domain |
| 5 | Three layers: domain, application, adapters | Asked for Clean Architecture, and it lets a future web runner reuse the session | Moderate: it shapes the package layout |
| 6 | Full annotations and `check_untyped_defs` on the new packages | The looser setting let D9 through | Easy: config |
| 7 | CLAUDE.md, both specs, and the README are updated | Constitution IV ties behaviour to the specs | Easy |
| 8 | `rooms.ravel` is deleted | It's orphaned, its predicate never holds, it duplicates `foyer.ravel`, and it fails on 1.0 | Trivial: `git restore` |
| 9 | `end` syntax is `- end: <outcome>`, label optional | Keyed-directive family, maps to the VM spec's `HALT(reason)`, and gives tests a stable label | Easy before release: one rename |
| 10 | CLI save/load: `save [FILE]` / `load [FILE]` (default `ravel-save.json`, overwrite), plus `--load FILE` | Plain words, the least surprising file location, and it lives only in the adapter | Easy |
| 11 | A refused load keeps the live game, and a refused `--load` exits non-zero | Never lose a live game to a bad file | Easy |
| 12 | The engine and saves use location IDs, never menu indices | Stable across menu order, which is why D17 can wait | Moderate: it's the save-format contract |
| 13 | A minimal fixture story is added for the gather, dead-end, given-once, and end-in-choice cases | Cloak can't exercise them | Easy |
