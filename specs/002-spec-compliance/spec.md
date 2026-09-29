# Feature Specification: Ravel Spec Compliance

**Feature Branch**: `002-spec-compliance`
**Created**: 2026-09-28
**Status**: Draft
**Beads Epic**: `ravel-h6v`
**Beads Phase Tasks**: plan `ravel-h6v.1` · red-team `ravel-h6v.2` · tasks `ravel-h6v.3` · analyze `ravel-h6v.4` · implement `ravel-h6v.5` · harden `ravel-h6v.6`
**Brainstorm**: specs/brainstorms/2026-09-28-spec-compliance-requirements.md
**Input**: The plan David approved on 2026-09-28. It reads: "The goal is a fully working Ravel
language as specified. The VM needs to be deterministic, have savable state, implement the whole
language, and be I/O-free, so it can drop into any application. That means realtime, async and
HATEOAS must all stay possible, with a clean/hexagonal (ports and adapters) architecture. The VM
doesn't have to match its spec's details as long as it keeps the spirit, and the VM spec should be
rewritten to match the engine. Rewrite as little of either as possible. When in doubt, favor
working, tested, well-architected code over the spec."

**Implementation-detail note.** This feature is about conformance to two documents, so it names
language syntax, spec sections and the engine's public entry points. Those are part of *what* is
being built. Class names, grammar rules and algorithms are left to planning.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Expressions compute what the spec says (Priority: P1)

As a story author, I write arithmetic, negative numbers, empty strings, quality references and
`value` in operations and comparisons. They compute the result the language spec documents.

**Why this priority**: Expressions sit under every operation and comparison. Today arithmetic
gives wrong answers silently, which is worse than a parse error. Quality references and `value`
fail outright. Constraints (US2) and the spec-as-tests suite (US6) both depend on this.

**Independent Test**: Compile and evaluate each expression form against a set of qualities, and
assert on the result. No story file is needed.

**Acceptance Scenarios**:

1. **Given** no qualities, **When** `X = 10 - 4 - 2` runs, **Then** X is 4.
2. **Given** no qualities, **When** `X = 8 / 4 / 2` runs, **Then** X is 1. `2 + 3 * 4` gives 14,
   and `*`, `/`, `//` and `%` share one precedence tier.
3. **Given** no qualities, **When** `X = -5` runs, **Then** X is -5. `Health > -1` parses and
   compares, and `X = -1.5` gives -1.5.
4. **Given** no qualities, **When** `X = ""` runs, **Then** X is the empty string.
5. **Given** `Health = 7` and `Bonus = 3`, **When** `X = [Health] + Bonus` runs, **Then** X is 10.
6. **Given** `Health` is unset, **When** `X = Health + 1` runs, **Then** X is 1.
7. **Given** `X = 10`, **When** `X += value * 2` runs, **Then** X is 30.
8. **Given** `Name = "Wearing Cloak"`, **When** the comparison `Name == "Wearing Cloak"` is
   tested, **Then** it's true, because a quoted token in an expression is a string.

---

### User Story 2 - Constraints clamp results (Priority: P1)

As a story author, I write `min` and `max` on an operation, and the result is clamped to the bound.

**Why this priority**: The spec documents constraints and the parser accepts them, but the engine
drops them. Authors get no error and a wrong value.

**Independent Test**: Apply constrained operations to known quality values, in a situation and in
a `given`, and assert on the stored value.

**Acceptance Scenarios**:

1. **Given** `X = 5`, **When** `X -= 10 min 0` runs, **Then** X is 0.
2. **Given** `X = 5`, **When** `X += 10 max 8` runs, **Then** X is 8.
3. **Given** `X = 5`, **When** `X += 1 max 8` runs, **Then** X is 6 (no clamp needed).
4. **Given** a rulebook whose `given` holds a constrained operation, **When** a new game starts,
   **Then** the given's stored value is clamped.

---

### User Story 3 - Rulebooks compile the way the spec describes (Priority: P2)

As a story author, a rule that starts with a registered concept name compiles as that concept even
without a `when:` after it. Stories whose rulebooks include each other load. `text:` inside a
`choice:` plays.

**Why this priority**: These are narrower gaps than US1 and US2. The first is a real mis-parse, and
the other two are shipped behavior with no test pinning them.

**Independent Test**: Compile small in-memory or fixture rulebooks and assert on the compiled
rules; load a two-rulebook include cycle and count loads.

**Acceptance Scenarios**:

1. **Given** a rule whose first item is `Situation` with no `when:` after it, **When** it
   compiles, **Then** it compiles as a Situation concept, not as intro text.
2. **Given** a rule whose first item is a one-word line that isn't a registered concept and has no
   `when:` after it, **When** it compiles, **Then** that line is intro text.
3. **Given** rulebook A includes B and B includes A, **When** the story loads, **Then** each
   rulebook is compiled exactly once, in breadth-first order, and loading ends.
4. **Given** a `choice:` with a `text:` entry, **When** the choice is offered and taken,
   **Then** the menu label is unchanged, and the `text:` is shown after the choice's own text, as
   §9.2 describes.

---

### User Story 4 - The engine embeds in any host (Priority: P2)

As an app developer, I compile a story from strings in memory, and I drive it through a stateless
request/response cycle. I can count on identical inputs giving identical results.

**Why this priority**: David's stated goal is a VM that drops into any application (realtime, async
or HATEOAS). The engine is already pure. This story removes the last filesystem assumption and
proves the property with tests.

**Independent Test**: Build a story from a mapping of names to source strings. Play it through
save-bytes → resume → choose → save-bytes with no session object. Replay the same choices twice and
compare.

**Acceptance Scenarios**:

1. **Given** a mapping of rulebook names to source strings, **When** an app compiles and starts a
   game from it, **Then** no filesystem access happens and the game plays.
2. **Given** a story environment constructed without naming a loader, **When** it's created,
   **Then** construction fails with a clear error, rather than silently reaching for the
   filesystem.
3. **Given** a saved game as bytes, **When** a handler resumes it, makes one choice and saves
   again, with no session held between requests, **Then** the new bytes resume to the same state
   the handler saw.
4. **Given** the same story and the same sequence of choices, **When** it's played twice, **Then**
   the outputs and the final state are identical (property-tested over generated choice sequences).
5. **Given** a game whose qualities hold a negative number, a float and `""`, **When** it's saved
   and resumed, **Then** every value comes back equal and of the same kind.

---

### User Story 5 - The docs describe the shipped system (Priority: P2)

As a story author or engine user, I read the language spec and the VM spec, and they describe what
the code does.

**Why this priority**: The rulings below resolve eight contradictions in the language spec. The VM
spec mostly describes a design that was never built, and it wrongly marks two features as
implemented.

**Independent Test**: Review each ruling against the language spec text, and each VM spec section
against the engine's public API.

**Acceptance Scenarios**:

1. **Given** the language spec, **When** read, **Then** it's v0.2, reflects rulings R1–R8, has a
   precedence and associativity table, and its PEG and Cloak listings match the code and
   `examples/cloak`.
2. **Given** the VM spec, **When** read, **Then** it's v0.2 and describes the domain model, the
   `start`/`choose`/`present`/`resume` API, the seven output types, the determinism and save
   guarantees, the ports and adapters, and host recipes for realtime, async and HATEOAS. The
   instruction-set design appears only in a short design-history appendix.
3. **Given** `CLAUDE.md`, **When** its "Language reference" paragraph is read, **Then** it matches
   both docs.

---

### User Story 6 - The spec can't drift again (Priority: P3)

As a maintainer, every expression, comparison and operation example in the language spec runs as a
test, so a change to either the code or the spec that breaks an example fails the build.

**Why this priority**: It's the guard that keeps US1–US5 true. It depends on US1, US2 and US5.

**Independent Test**: Run the spec-examples test module; then deliberately break one example in the
spec and confirm a test fails.

**Acceptance Scenarios**:

1. **Given** the language spec §4–§7, §9 and §11.4, **When** the spec-examples tests run, **Then**
   every expression, comparison and operation example there is exercised and passes.
2. **Given** one spec example is edited to a wrong expected result, **When** the tests run,
   **Then** a test fails naming that example.

---

### Edge Cases

- `X = 10 - -4` gives 14. The first `-` is binary and the second starts a negative literal.
- `X = 10-4` (no spaces) gives 6. Whitespace is optional around arithmetic operators (ruling R8).
- `X=5` without spaces around the setter is rejected. Whitespace is required around setters and
  comparators (ruling R8).
- `value` used where there's no subject quality (outside an operation or comparison) is a compile
  error, not a runtime crash.
- An operation takes at most one constraint, and its bound is a number literal (§7.3, §10.1).
  `X += 1 min 0 max 8` stays a parse error; stacking bounds would be a new feature.
- A constraint on a string-valued result is a compile or runtime error with a clear message, not a
  silent pass-through.
- A quality reference to an unset quality reads 0, including inside `value`-free arithmetic.
- An include cycle of length 3 (A → B → C → A) loads each rulebook once.
- A save holding a quality set to `""` resumes to `""`, not to unset or 0.
- `value`, `min` and `max` remain usable as subject names (`value = 3`), even though they're
  reserved inside expressions (ruling R4).

## Requirements _(mandatory)_

### Functional Requirements

**Expressions (US1)**

- **FR-001**: Arithmetic MUST be left-associative, with `*`, `/`, `//` and `%` on one tier binding
  tighter than `+` and `-`.
- **FR-002**: Negative integer and float literals MUST parse, and binary minus MUST keep working.
- **FR-003**: The empty string `""` MUST parse as a string literal.
- **FR-004**: An identifier or `[Bracketed Name]` in an expression MUST read the named quality's
  current value, or 0 if it's unset.
- **FR-005**: A double-quoted token in an expression MUST be a string literal. Quoted names MUST
  stay valid as the subject of a comparison or operation.
- **FR-006**: `value` in an expression MUST evaluate to the subject quality's current value, in
  both operations and comparisons.
- **FR-007**: `value`, `min` and `max` MUST be reserved inside expressions only, and MUST stay
  valid as subject names.

**Constraints (US2)**

- **FR-008**: A `min` bound MUST raise a result below it to the bound, and a `max` bound MUST lower
  a result above it to the bound. This applies to operations in situations and in `given`.

**Compiler and loader (US3)**

- **FR-009**: A rule's first item MUST compile as a concept declaration if a `when:` follows it or
  if it exactly names a registered concept handler. Otherwise it MUST compile as intro text.
- **FR-010**: Include cycles MUST load, with each rulebook compiled once, in breadth-first order.
- **FR-011**: `text:` inside `choice:` MUST have a test pinning its documented behavior.

**Embeddability (US4)**

- **FR-012**: An app MUST be able to compile and play a story from in-memory source strings,
  through both the compile layer and the application layer's story-source port.
- **FR-013**: The story environment MUST take its loader as a required, injected dependency. The
  core MUST NOT default to a filesystem adapter.
- **FR-014**: A save MUST round-trip through bytes so that a stateless handler can resume, choose
  and save again with no session object held between requests.
- **FR-015**: The engine MUST be deterministic: identical story and choices give identical outputs
  and state.
- **FR-016**: Saves MUST preserve negative numbers, floats and `""` exactly, value and kind.

**Documentation (US5)**

- **FR-017**: The language spec MUST be updated to v0.2, applying rulings R1–R8, adding a
  precedence and associativity table, and resyncing §10.1 (PEG) and §12 (Cloak) with the code.
- **FR-018**: The VM spec MUST be rewritten as v0.2 to describe the shipped engine and its ports,
  including realtime, async and HATEOAS host recipes, with the instruction-set design cut to a
  design-history appendix.
- **FR-019**: The `CLAUDE.md` "Language reference" paragraph MUST match both docs.

**Spec-as-tests (US6)**

- **FR-020**: Every expression, comparison and operation example in language spec §4–§7, §9 and
  §11.4 MUST run as a test.

### Spec-Contradiction Rulings

Decided under the "favor working, tested, well-architected code" rule. Each becomes a dated
decision in `research.md`, per Constitution Principle IV.

| # | Contradiction | Ruling |
|---|---|---|
| R1 | §3.1 forbids circular includes, but `examples/cloak` has them | Cycles allowed; each rulebook loads once, breadth-first. Fix the spec. |
| R2 | §3.1 claims include order affects rule order, and "later includes take precedence" | Drop both claims. State the real ordering (score, then location descending). For `given`, later-loaded values win. |
| R3 | §5.2 calls `"Wearing Cloak"` a quality reference; §4.2/§10.1 make it a string | In expressions, a quoted token is always a string. Quality refs are identifiers or `[Bracketed Name]`. Quoted names stay valid as subjects. |
| R4 | §4.1 says "no reserved words"; Appendix A reserves `value`, `min` and `max` | Reserved inside expressions only; still valid as subject names. |
| R5 | §9.1's example output contradicts its stated `[.]` rule | The rule wins; fix the example. |
| R6 | §8.1's optional concept line is ambiguous with one-word intro text | See FR-009. Document it. |
| R7 | Can a rule's first line use `{cond}` or `<>`? | No. The first line uses intro syntax only. Document it; no code change. |
| R8 | Whitespace around operators is unspecified | Required around setters and comparators, optional around arithmetic operators. Document it. |

### Key Entities

- **Expression**: A value computed from literals, quality references, `value` and arithmetic.
  Evaluated against the current qualities and, inside an operation or comparison, its subject's
  current value.
- **Quality reference**: A name inside an expression that reads a quality's current value.
- **Constraint**: A `min` or `max` bound attached to an operation, applied to its result.
- **Story source**: Where rulebook text comes from. A filesystem directory or an in-memory mapping
  are the two shipped adapters.
- **Saved game**: The byte form of a game state. Enough on its own to resume play in a fresh
  process.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of the expression, comparison and operation examples in the language spec run as
  passing tests.
- **SC-002**: All eight probe regressions from the 2026-09-28 audit pass as tests (the US1 and US2
  acceptance scenarios cover them).
- **SC-003**: A story plays end to end from in-memory text with zero filesystem reads.
- **SC-004**: Playing any generated choice sequence twice gives identical results in every trial
  run.
- **SC-005**: The example story Cloak of Darkness plays through to both endings.
- **SC-006**: Zero sections of the VM spec describe unbuilt behavior without a "deferred" or
  "design history" label.
- **SC-007**: The full quality gate stays green: every test passes at 100% branch coverage, with
  lint, format and type checks clean.

## Assumptions

- Builds on the landed 001-reentrant-vm: the pure engine, save format v1, `GameSession`, and the
  `StorySource`/`SaveStore` ports with filesystem adapters.
- `hypothesis` is already a dev dependency, so FR-015's property test adds no new dependency.
- No new language features beyond what the spec documents. No instruction-set VM, JSON IR or
  alternate execution modes. No realtime, async or HATEOAS host adapters ship; the VM spec
  documents recipes, and one acceptance test proves the HATEOAS cycle.
- The save format stays at version 1 unless FR-016 forces a change; planning records why if it
  does.

### Deferred to Planning

- **[FR-013]** Removing the environment's default loader breaks `Environment()` callers. That's a
  Constitution Principle VI public-API change, so the plan's Constitution Check must list it with
  the rejected non-breaking alternative.
- **[FR-001–FR-007]** The grammar rewrite must keep regex backslashes doubled and keep
  `tests/test_grammars.py` passing. Every grammar task needs this as an explicit acceptance
  criterion.
- **[FR-016]** Confirm whether save format v1 already encodes negatives, floats and `""` exactly.
- **[FR-004]** Decide how a bracketed name in an expression is told apart from the `[bracketed]`
  intro-text syntax, if the two grammars ever meet.
- **[Edge cases]** Confirm the behavior of a constraint on a string result and of `value` outside
  an operation or comparison. The edge cases above propose clear errors.

## Clarifications

### Session 2026-09-28

- Q: Use the brainstorm doc as input? → A: Yes. The approved plan seeds it, and its rulings are
  decided.
- Q: Any open product questions before specifying? → A: None. David's rule, "favor working, tested,
  well-architected code over the spec", settles R1–R8. Stop and ask only for a new contradiction
  it can't settle.
