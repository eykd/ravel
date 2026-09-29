# Implementation Plan: Ravel Spec Compliance

**Branch**: `002-spec-compliance` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-spec-compliance/spec.md`
**Beads**: epic `ravel-h6v`, this phase `ravel-h6v.1`

## Summary

Make the compiler and engine do what `docs/RAVEL_LANGUAGE_SPEC.md` says, then make both specs
describe what the code does. The expression grammar gets rebuilt as two left-folding repetition
tiers with signed literals, empty strings, quality references and a working `value`. Operations
apply their `min`/`max` constraints. The compiler recognizes a bare registered concept line.
`Environment` takes its loader as a required dependency, and a new in-memory loader and story
source let an app play a story with no filesystem. Tests pin include cycles, `text:` in choices,
the stateless save/resume/choose cycle, determinism and save value kinds. The language spec goes to
v0.2 (rulings R1–R8), the VM spec is rewritten as v0.2 around the shipped engine, and a test module
reads the language spec and runs its examples so the two can't drift again.

The governing rule, from David on 2026-09-28: favor working, tested, well-architected code over
the spec, and rewrite as little of either document as possible.

## Technical Context

**Language/Version**: Python 3.14 (`.python-version`, `requires-python = ">=3.14"`)
**Primary Dependencies**: parsimonious (PEG), syml (rulebook YAML), attrs, python-slugify, click
(CLI). No new runtime dependency.
**Storage**: save files, format v1, unchanged (research PD-14)
**Testing**: pytest + pytest-cov (100% branch), hypothesis (dev, already present). Acceptance tests
are plain pytest in `tests/acceptance/spec_compliance/` (PD-15)
**Target Platform**: library consumers of `ravel.engine`/`ravel.app`, plus the `ravel run` CLI
**Project Type**: library + console script
**Performance Goals**: none new. The determinism property test (200 examples) must finish in
under 30 s locally, like 001's
**Constraints**: domain core stays I/O-free; 100% branch coverage; ruff, mypy, pre-commit clean.
`ravel.types`, `ravel.queries` and `ravel.engine.*` are **strict** mypy modules, so `QualityRef`,
`Value`, `Constraint.apply` and the changed `evaluate` signatures need full annotations;
`grammars.py`/`parsers.py`/`compiler/` are "stay clean" (Principle II). Grammar text keeps doubled
backslashes (PD-17)
**Scale/Scope**: 1 grammar rewritten (expression half of `base_expression_grammar`), ~6 visitor
methods, 3 new types (`QualityRef`, `Value`, `MemoryLoader`) and 1 new adapter
(`MemoryStorySource`), 3 new errors, 1 compiler branch, 2 spec docs revised, ~6 acceptance test
files, 1 spec-examples test module

No open clarifications remain; see research.md.

## Brainstorm Context

**Source**: [specs/brainstorms/2026-09-28-spec-compliance-requirements.md](../brainstorms/2026-09-28-spec-compliance-requirements.md)

### Key Decisions Carried Forward

- Favor working, tested, well-architected code over the spec, then fix the spec to match. Applied
  as rulings R1–R8 (research.md).
- Rewrite the VM spec to match the engine, not the reverse (PD-18).
- Spec examples become tests, so drift fails the build (PD-16).
- Save format stays v1 unless the new value kinds force a change. They don't (PD-14).

### Scope boundaries (non-goals)

- No language features beyond what the spec documents: no unary minus on references or groups, no
  stacked constraints, no expression-valued bounds.
- No instruction-set VM, JSON IR, layered qualities or alternate execution modes. They stay in the
  VM spec's design-history appendix.
- No realtime, async or HATEOAS host adapters ship. The VM spec documents recipes; one acceptance
  test proves the HATEOAS cycle.
- No *new per-failure* error types for arithmetic (`1 / 0`, `"a" + 1`). Red-team pass 1 amends
  PD-08: those failures are now wrapped at the existing choke points (operations →
  `InvalidOperationError`; predicates → no match), because quality references make them reachable
  from ordinary story text. See Edge Cases & Error Handling.

### Deferred Questions (resolved during planning)

- FR-013 is a Principle VI break → listed below with the rejected alternatives (PD-12).
- Grammar rewrite must keep doubled backslashes → an explicit acceptance criterion on every grammar
  task (PD-17, contracts/expression-grammar.md).
- Does save v1 already round-trip negatives, floats and `""`? → Yes, verified by probe; test-only
  (PD-14).
- Bracketed names vs `[bracketed]` intro text → the grammars never meet; documented (PD-05).
- A constraint on a string result → `ConstraintError` at run time, `OperationParseError` at compile
  time for a string literal (PD-08). `value` outside an operation or comparison → unreachable by
  grammar (PD-07).

## Constitution Check

_GATE: passed before Phase 0; re-checked after Phase 1 (below)._

| Principle | Status | Notes |
|---|---|---|
| I. TDD (NON-NEGOTIABLE) | PASS | Every task starts RED, committed via `.venv/bin/python -m tools.commit_red <task-id>`. Doc-only tasks (US5) are gated by US6's spec-examples test and the acceptance checks listed below. The two right-nested parser tests change as part of the RED for the left-fold task. |
| II. Type Safety | PASS | New code in strict modules (`types.py`, `queries.py`, `engine/*`, `adapters/*`) is fully annotated. `QualityLookup` is a `Protocol`, so `Qualities` and `dict` both type-check without a cast. |
| III. Coverage & Lint | PASS | 100% branch kept; no `# pragma: no cover`. |
| IV. Spec discipline | PASS | Every behavior change cites a spec section or FR (see Spec Conformance). Every open spec question is a dated decision in research.md (R1–R8, PD-01–PD-18). Spec edits land in the same commits as the behavior. |
| V. Simplicity / YAGNI | PASS, one row in Complexity Tracking | No new dependency. Grammar stays one shared `base_expression_grammar`; `ComparisonParser` stops duplicating it (PD-17). New value types (`QualityRef`, `Value`) go in `types.py`. |
| VI. Public API Stability | **BREAK (listed)** | See below. |
| VII. Clean Architecture | PASS (improved) | `environments.py` stops importing the filesystem loader, so VII's list grouping it with "the file-based loaders" goes stale; a PATCH amendment (wording only, no principle change) rides the FR-013 commit, as 001 did for its stale file lists. `MemoryLoader` has no I/O. `types.py` gains an import of `ravel.exceptions` (domain → domain), made cycle-free by `exceptions.py` importing `Source` from `syml.basetypes`. The engine still imports nothing from `ravel.app`/`ravel.adapters` (`tests/engine/test_layering.py`). |

### Principle VI: breaking and semantic changes

| Surface | Change | Rejected non-breaking alternative |
|---|---|---|
| `Environment(loader=...)` | `loader` is required; `Environment()` raises `TypeError` (FR-013, PD-12) | (a) Keep `FileSystemLoader()` as the default with a `DeprecationWarning`: the core keeps importing the filesystem adapter, and a forgotten argument still silently reads the working directory, which is exactly what FR-013 bans. (b) Default to `MemoryLoader({})`: construction succeeds and `load()` fails later with a confusing `RulebookNotFound('begin')`. |
| Compiled rulebook: expression trees | Now left-nested (`10 - 4 - 2` was `10 - (4 - 2)`) | None: the old shape computed wrong answers (FR-001). |
| Compiled rulebook: `[Name]` in an expression | Now `QualityRef("Name")`; was the string `"Name"` | Keep brackets as strings on the right-hand side: contradicts §4.1/§5.2 and FR-004. No in-repo story relies on the old reading. |
| Compiled rulebook: `value` | `types.VALUE` is now a singleton instance, not a class | None: the class form crashed at run time. Equality with `types.VALUE` still holds. |
| Operation semantics | `min`/`max` now clamp | None: the spec always said so (FR-008). |
| `ravel.engine` errors | `start`/`choose` can raise the new `InvalidOperationError(EngineError)`, for a `ConstraintError` **and** for a `ZeroDivisionError`/`OverflowError`/`TypeError` from an operation's arithmetic (red-team RT-1) | Let `ConstraintError` escape unwrapped: engine callers would need a second `except`. Let arithmetic errors escape raw (PD-08 as first planned): `X = 100 / Bonus` with `Bonus` unset now divides by zero from ordinary story text, and a raw `ZeroDivisionError` bypasses `GameSession`'s `EngineError` handling. |
| Condition evaluation failures | A comparison (a `when:` predicate or a `{…}` line prefix) whose evaluation raises `TypeError`, `ArithmeticError` or `EvaluationError` is false, logged at `WARNING`; the catch lives in `Comparison.check`/`__call__`. Today only `query_predicates`' unset-subject branch catches `TypeError`; a set subject or a `{…}` prefix crashes (red-team RT-2, RT-10) | Raise a typed `EngineError` instead: every query on that state would raise, so a save sitting in that state could never be played again (US4's stateless resume). |

Unchanged: `Loader` (`BaseLoader.load`/`get_source`), the compiled rulebook's dict shape, `Source`/
`Pos`, `start`/`choose`/`present`/`resume` signatures, output and state types, `GameSession`, save
format v1.

**Post-design re-check (after Phase 1)**: still PASS with the one listed break. Phase 1 added no
dependency, no new grammar dialect, and no layer crossing.

## Spec Conformance

| Change | Spec section touched | Changes the spec? |
|---|---|---|
| Left-assoc, one `* / // %` tier (FR-001) | Language §5.1, §10.1 | Yes: add a precedence and associativity table and result lines (`10 - 4 - 2 → 4`) |
| Signed literals (FR-002) | §4.2, §5.1, §7.3, §10.1 | Yes: note literal-only sign; `10 -4` is subtraction; bounds may be negative |
| `""` (FR-003) | §4.2, §10.1 | Yes: `~'[^"]*'` in §10.1 (already so); state `""` is allowed |
| Quality refs (FR-004, R3) | §4.1, §5.2, §10.1 | Yes: identifiers and `[Bracketed]` in expressions; quoted tokens are strings; `[Has-Key]` for punctuated names, with the warning that bare `Has-Key` is subtraction and the result line `Has-Key = 5 ; X = [Has-Key] → 5` (RT-3) |
| Quoted tokens are strings (FR-005, R3) | §5.2 | Yes: replace `"Wearing Cloak"` with `[Wearing Cloak]` in the term list |
| `value` (FR-006) | §4.3 | Only a sentence: `value` is 0 for an unset subject; works in comparisons too |
| Reserved words (FR-007, R4) | §4.1, Appendix A | Yes: "no reserved words in subject position" |
| Constraints (FR-008) | §7.3, §10.1 | Yes: one per operation; applies to `=` and `given`; string result is an error; clamped value takes the bound's kind |
| Concept line (FR-009, R6) | §8.1, §8.2 | Yes: the detection rule and its one-word-intro trade-off |
| Include cycles, ordering (FR-010, R1, R2) | §3.1, §3.2 | Yes: cycles allowed, BFS, real ordering, later `given` wins |
| `text:` in `choice:` (FR-011) | §9.2 | One sentence: "(optional additional text)" already matches (PD-10); v0.2 adds that the bracketed line must be the choice's first item (RT-5) |
| `[.]` example (R5) | §9.1 | Yes: fix the tail comment |
| First line intro-only (R7) | §9.1 | Yes: one sentence |
| Whitespace (R8) | §6.2, §7.2 | Yes: one sentence each |
| §6.2 examples nested under `when:` (PD-16) | §6.2 | Yes: one-line edit so the extractor can classify them |
| §12 Cloak listing (FR-017) | §12 | Yes: show all five `examples/cloak` files verbatim (today three, with a stale `begin.ravel`); a US5 test compares each listing to its file |
| Version (FR-017) | header, §14 | Yes: 0.2, dated 2026-09-28 |
| Embedding, determinism, saves (FR-012–FR-016) | VM spec (all) | Yes: v0.2 rewrite (PD-18) |
| `CLAUDE.md` "Language reference" (FR-019) | — | Yes: VM spec is no longer "annotated 0.1"; name the v0.2 docs |

Open spec questions settled in research.md: R1–R8 and PD-05, PD-07, PD-08, PD-09, PD-10.
Relevant history: `52a9c7b` (VM spec §0 status table, which wrongly marked Expression/Constraint
implemented), `300a2df` (`end` in §9.4), `12180c4` (syml 1.0 re-indent).

## Project Structure

### Documentation (this feature)

```text
specs/002-spec-compliance/
├── plan.md               # this file
├── research.md           # R1–R8 rulings, PD-01–PD-18
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── expression-grammar.md   # FR-001–FR-007
│   ├── evaluation.md           # FR-004–FR-008
│   ├── rulebook-compile.md     # FR-009–FR-011
│   ├── embedding.md            # FR-012–FR-016
│   └── spec-examples.md        # FR-020
└── tasks.md              # sp:05-tasks (not created here)
```

### Source Code (repository root)

```text
src/ravel/
├── grammars.py              # expression half of base_expression_grammar rewritten (PD-01–PD-04)
├── parsers.py               # left fold, QualityRef/VALUE visitors, constraint-on-string check;
│                            #   ComparisonParser uses grammars.comparison_grammar
├── types.py                 # QualityRef, Value/VALUE, QualityLookup, EMPTY_QUALITIES,
│                            #   Constraint.apply, evaluate(..., qualities, qvalue)
├── exceptions.py            # EvaluationError, ConstraintError; Source from syml.basetypes
├── queries.py               # pass qualities into predicates
├── environments.py          # loader required; no ravel.loaders import
├── loaders.py               # MemoryLoader
├── compiler/
│   ├── concepts.py          # is_registered()
│   └── rulebooks.py         # bare registered concept branch
├── engine/
│   ├── engine.py            # _apply_operation wraps EvaluationError
│   └── errors.py            # InvalidOperationError
└── adapters/
    └── story_source.py      # MemoryStorySource

docs/
├── RAVEL_LANGUAGE_SPEC.md   # v0.2
└── RAVEL_VM_SPEC.md         # v0.2 rewrite

tests/
├── test_parsers.py          # left-nested expectations; new grammar cases
├── test_types.py            # evaluation, constraints; Comparison.check/__call__ soft-fail (RT-10)
├── test_queries.py          # references in predicates; predicate failures are non-matches (RT-2),
│                            #   `except TypeError` fallback deleted (RT-10);
│                            #   its bare Environment() (line 67) passes a loader
├── test_compiler_rulebooks.py   # concept detection
├── test_compiler_concepts.py    # its bare Environment() (line 29) passes a loader
├── test_environment.py      # required loader, cycles
├── test_loader.py           # MemoryLoader
├── spec_examples.py         # new helper: extract_examples / run_example (PD-16)
├── test_spec_examples.py    # new (PD-16)
├── conftest.py              # Environment() callers pass a loader (the `Environment()` fixture at
│                            #   line 18; with test_queries.py and test_compiler_concepts.py these
│                            #   are the only bare callers, per `rg 'Environment\(\)'`)
├── adapters/test_story_source.py   # MemoryStorySource
└── acceptance/spec_compliance/     # new package (PD-15)
    ├── __init__.py
    ├── test_us01_expressions.py
    ├── test_us02_constraints.py
    ├── test_us03_rulebooks.py
    ├── test_us04_embedding.py
    ├── test_us04_determinism_property.py
    ├── test_us05_docs.py
    └── test_us06_spec_examples.py
```

**Structure Decision**: single library, existing layout. Acceptance tests get their own subpackage
because 001 already uses `tests/acceptance/test_us01_*.py` … `test_us06_*.py`.

## Acceptance Test Strategy

Plain pytest end-to-end tests, marked `@pytest.mark.acceptance`, each docstring naming its scenario
(`"""US1-AS5: …"""`), per research PD-15 (and 001's PD-15). **Not** Gherkin: the
`specs/acceptance-specs/*.feature` pipeline in the plan template doesn't exist in ravel and isn't
added, so `sp:05-tasks` should create the `.py` files below instead of `.feature` files. They drive
public surfaces only: `ravel.parsers` + `ravel.types` for expression semantics, `Environment` with
`MemoryLoader`, `ravel.engine`, `ravel.app.saves`, `GameSession`, and file reads of the two docs.

| User Story | Acceptance test file | Drives | Scenarios |
|---|---|---|---|
| US1: expressions | `tests/acceptance/spec_compliance/test_us01_expressions.py` | parsers + `evaluate`; a one-file story through `engine.start` for AS5/AS7; plus the RT-1 arithmetic-failure checks (`InvalidOperationError`) | 8 (+2 RT-1) |
| US2: constraints | `tests/acceptance/spec_compliance/test_us02_constraints.py` | situation effect via `engine.choose`; `given` via `engine.start` | 4 |
| US3: rulebooks | `tests/acceptance/spec_compliance/test_us03_rulebooks.py` | `Environment(MemoryLoader)`; counting loader for AS3; engine for AS4 | 4 |
| US4: embedding | `tests/acceptance/spec_compliance/test_us04_embedding.py` (AS1, AS2, AS3, AS5), `test_us04_determinism_property.py` (AS4; hypothesis, `max_examples=200`, `deadline=None`, `derandomize=True`, `database=None`) | `MemoryStorySource`, filesystem calls patched to raise; stateless handler | 5 |
| US5: docs | `tests/acceptance/spec_compliance/test_us05_docs.py` | reads both docs and `CLAUDE.md`: versions are 0.2; §5.1 has the precedence table; each ruling's key sentence is present; §12 shows **all five** `examples/cloak/*.ravel` files and each listing equals its file's text (today it shows three, and its `begin.ravel` is out of date); VM spec names `start`/`choose`/`present`/`resume`, all seven output types, the three host recipes, and has a design-history appendix | 3 |
| US6: spec can't drift | `tests/acceptance/spec_compliance/test_us06_spec_examples.py` | AS1 is thin: it asserts `extract_examples` finds examples in every scoped section and that none of them fails (one loop, not a second parametrization of `tests/test_spec_examples.py`); AS2 runs the extractor over a copy with one result edited, asserting the failure names the example | 2 |

**§12 listing check (US5), pinned.** Today §12 (`docs/RAVEL_LANGUAGE_SPEC.md` lines 666–741) has
three `### <file>.ravel` headings (`begin`, `foyer`, `cloakroom`), each followed directly by one
` ```yaml ` fenced block; `examples/cloak/` has five files, each ending in exactly one `\n`. The
test in `test_us05_docs.py`:

1. Slices the text from the `## 12.` heading to the next `## ` heading.
2. Collects the `### ` headings in that slice, in order, and asserts they equal
   `["begin.ravel", "foyer.ravel", "cloakroom.ravel", "bar-dark.ravel", "bar-light.ravel"]`
   (the `include:` order in `begin.ravel`). It also asserts the set equals
   `{p.name for p in Path("examples/cloak").glob("*.ravel")}`, so a sixth file fails the test.
3. For each heading, takes the first fenced block after it: the lines strictly between its opening
   fence and the next line that is exactly ` ``` `. It asserts `"\n".join(lines) + "\n" ==
   (CLOAK / name).read_text()`. No other normalization, so drift in whitespace fails too.

This check is separate from the US6 extractor, which ignores §12 (contracts/spec-examples.md,
Scope). The §12 edit and this test land together in one US5 task.

**Regression checks folded into the gate**: SC-005 (Cloak plays to both endings) is 001's
`tests/acceptance/test_us06_end_to_end.py`, which must stay green through the grammar rewrite.
`examples/cloak`, `examples/taxi` and `tests/fixtures/stories/*` use only `+= 1` and `= "…"`
forms (grep, 2026-09-28), so the rewrite shouldn't change them; the grammar task still runs the
whole suite, not just the parser tests.

## Suggested implementation order

1. Errors and the import-cycle fix (`exceptions.py`), `QualityRef`/`Value`/`QualityLookup`,
   evaluation context threading through `types.py` and `queries.py` (US1 value/refs semantics).
2. Grammar rewrite + visitors (US1), with PD-17's criterion, then the two expected test edits.
3. Constraints: `Constraint.apply`, compile-time string check, `_apply_operation` wrapping (US2).
4. Concept detection; pin include cycles and `text:` in choices (US3).
5. `MemoryLoader`, `MemoryStorySource`, required loader and caller updates (US4 AS1/AS2), then the
   stateless-cycle, determinism and save-kind tests (AS3–AS5).
6. Language spec v0.2 edits, each landing with the behavior it documents (Principle IV), then the
   spec-examples test (US6), then the VM spec v0.2 rewrite and `CLAUDE.md` (US5).

## Security Considerations

### Trust boundaries (VM spec v0.2 §8–§10)

- **Saves are not tamper-evident (RT-4).** `decode_save` checks shape and the 1 MiB cap and
  nothing else; `resume` accepts any well-formed qualities and stack. In the HATEOAS recipe the
  bytes may travel through the client (a hidden field, a URL, a cookie), so a player can forge any
  quality. The engine can't fix this and shouldn't: integrity is the host's job. VM spec §10's
  HATEOAS recipe MUST say so and name the two options: keep saves server-side behind an opaque id
  (`SaveStore`), or authenticate the bytes in the host adapter (HMAC over the save, key held by the
  server) before `decode_save`. `choose` already refuses a location that isn't in
  `state.offered` (`NotOfferedError`), so a forged *location* can't skip the menu; a forged *save*
  can. contracts/embedding.md's stateless recipe carries the same note. No code change.
- **Story sources are trusted input (RT-8).** The compiler isn't hardened against hostile rulebooks:
  deeply nested parentheses reach Python's recursion limit inside parsimonious and raise
  `RecursionError`, not `ParseError`, and a long flat expression builds an equally deep
  left-nested tree for `evaluate`. VM spec §9 states that `StorySource`/`Loader` inputs are authored
  content, and that a host compiling untrusted rulebooks must isolate compilation (process, time
  and memory limits). Pre-existing; no code change.

## Edge Cases & Error Handling

### Arithmetic failures now reachable from story text (RT-1, RT-2)

FR-004 makes an unset quality read 0 and lets a string-valued quality appear in arithmetic. So
`X = 100 / Bonus` (Bonus unset) divides by zero, and `X = Name + 1` (Name a string) raises
`TypeError`, from text an author writes routinely. PD-08 deferred these while divisors could only
be literals; references change that, so this pass amends PD-08 at the two existing choke points,
adding no new per-failure error type:

- **Operations (RT-1).** `_apply_operation` catches `(EvaluationError, ArithmeticError, TypeError)`
  and raises `InvalidOperationError("%r failed: %s" % (operation, error))`, chaining the cause
  (`Operation` has no source text, so the message uses its attrs `repr`). `ArithmeticError`
  covers `ZeroDivisionError` and `OverflowError` (`1e308 * 10` stays `inf`, which `Qualities.set`
  already rejects with `InvalidQualityValueError`). Tests: US1 acceptance adds `X = 100 / Bonus`
  with Bonus unset → `InvalidOperationError` whose `__cause__` is a `ZeroDivisionError`, and
  `X = Name + 1` with `Name = "a"` → `InvalidOperationError` from `TypeError`; a `GameSession`
  test shows the session's state is untouched after either.
- **Conditions (RT-2, placed by RT-10).** A comparison is evaluated from three sites, not one:
  `when:` predicates in `query_predicates` (both the set-subject branch and the unset-subject
  `predicate(0)` fallback), and a text line's `{…}` prefix via `Text.check` in `_Run.text`. Pass 1
  covered only the first; `{X > 10 / Y}Low.` would still raise a raw `ZeroDivisionError` out of
  `choose`. So the soft failure lives in `Comparison` itself, the one type all three sites call:
  `Comparison.check(qualities)` and `Comparison.__call__(qvalue, *, qualities)` catch
  `(TypeError, ArithmeticError, EvaluationError)`, log the comparison and the error at `WARNING` on
  the `ravel.query` logger, and return `False`. `Comparison.evaluate` still raises, so unit tests
  can see the underlying error. `query_predicates`' existing `except TypeError` becomes
  unreachable and is **deleted** (leaving it would break the 100% branch gate). This widens
  PD-06's fallback on purpose: a raising `when:` predicate is evaluated on every query, so raising
  would make every `present`/`choose` from that state fail and strand any save sitting in it, and
  US4's stateless handler has no session to recover with. Operations fail loud (they run once per
  action and the host can report it); conditions fail soft (a failing `when:` is a non-match, a
  failing `{…}` prefix hides its line). Tests: `when: X > 10 / Y` with X set and Y unset → the rule
  doesn't match and the other rules still do; `when: X > Name` with `Name = "a"` → no match, where
  today it raises; `{Health > 10 / Y}Hidden.` with Y unset → the line isn't shown and play
  continues; `caplog` sees one `WARNING` per failing evaluation.
- **Test discipline.** Because `TypeError` is now wrapped, a future bug of the old
  `VALUE`-class kind would surface as `InvalidOperationError`, not as a crash. US1 and US2
  acceptance tests assert computed *values* (and kinds), never just "no exception raised".

### Silent wrong answers from bare punctuated names (RT-3)

A subject is `[^\s]+`, so `Has-Key = 5` stores the quality `Has-Key`. In an expression, R8 makes
whitespace around arithmetic optional, so `X = Has-Key` parses as `QualityRef("Has") -
QualityRef("Key")` and gives 0 with no error: the exact silent-wrong-answer class this feature
exists to remove. The grammar stays as designed (R8 is decided), and the trap is made visible and
pinned:

- contracts/expression-grammar.md gets rows for `X = Has-Key` (subtraction) and `X = [Has-Key]`
  (one reference).
- Language spec §4.1 and §5.2 say it in one sentence each: "In an expression, a name with
  punctuation must be bracketed: `[Has-Key]`. `Has-Key` is `Has` minus `Key`."
- §5.2 gets the result line `Has-Key = 5 ; X = [Has-Key] → 5`, so US6 runs it.

### `text:` placement inside `choice:` (PD-10, RT-5)

Confirmed by probe (2026-09-28): with the `[Go]…` line first, `text:` is additional text shown after
the choice's own text and before its effects; the label is unchanged. With `text:` *first*, compile
fails with a bare `ParseError("No text found, instead: {…}")`. §9.2's structure block already shows
the bracketed line first; v0.2 adds "The bracketed line must be the choice's first item." and
contracts/rulebook-compile.md lists the rejected order. No code change: US3's test pins that
compiling it raises `ravel.exceptions.ParseError` and that the message carries the `Source`
position (`Line 4, Column 8` in the probe).

### Soft-failing conditions stay visible to authors (RT-12)

RT-10 turns a broken condition into a quiet `False`. The only signal is the `WARNING` on
`ravel.query`, and a failing `when:` logs on every query, every turn. VM spec §6 and language spec
§6.3 each get one sentence: a condition that can't be evaluated is false and logs a warning. The
`ravel run` console adapter already configures logging at `WARNING` by default (`cli.main`), so
authors see these on stderr with no flag; no dedup or rate limit is added (log volume is the
host's policy). Low; docs only.

### Spec examples must use the raising path (RT-11)

RT-10 makes `Comparison.check`/`__call__` return `False` on an evaluation error. The US6 runner
would then pass a spec comparison example that can't evaluate (`X > "a"` against 0) as "checked
without raising". contracts/spec-examples.md pins `run_example` to `Comparison.evaluate`, which
still raises, for both comparison items and comparison result lines.

### Kind-sensitive assertions (RT-6)

Frozen-attrs `==` has the `1 == 1.0` (and `True == 1`) blind spot 001's property test already notes.
Every test that pins a *kind* asserts `type(...)` as well as value: the bound's-kind constraint rows
(`X -= 10 min 0.0` → `0.0`), `8 / 4 / 2` → `1.0`, US4-AS5's save kinds, and US4-AS4's determinism
check, which compares encoded save bytes in addition to `GameState` equality.

### Determinism test bounds

US4-AS4's route is a hypothesis list of choice indices (`max_size` 30, like 001's `MAX_STEPS`),
taken modulo the menu size; play stops at a halt or when the list runs out, so Cloak's
foyer↔cloakroom cycle can't make an example run forever.

### File reads in doc tests (RT-7)

`test_us05_docs.py`, `tests/test_spec_examples.py` and the §12 listing check read the spec,
`CLAUDE.md` and `examples/cloak/*.ravel` with `read_text(encoding="utf-8")`: the spec holds `→`,
Cloak holds `…`, and Python 3.14 isn't in UTF-8 mode by default on every platform. The §12 slicer
collects `### ` headings only from lines *outside* fenced blocks, so a future `### ` line inside a
listing can't split it.

## Performance Considerations

### Resource limits

- **Unbounded string growth (RT-9).** `X *= 2` on a string quality doubles it (`"ab" * 2`), and
  `Qualities.set` checks kind, not size. Thirty turns of that reach gigabytes in memory before
  `MAX_SAVE_BYTES` stops the *save*. Not fixed here (no spec text sets a limit, and a cap is a new
  language rule); VM spec §6 lists it under known limits, and the PD-08 follow-up issue covers it.
- **Query lookup cost.** `query_predicates` builds its `dict(query)` lookup once per call, which is
  once per rule per query. Acceptable at Cloak's scale (5 rulebooks, compile ≈ 9 ms, measured
  2026-09-28); building it once in `query()` is a later optimization, not part of this feature.
- The determinism property test compiles Cloak about 400 times (two per example); at ≈ 9 ms each
  it stays well inside the 30 s budget.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| New grammar rules (`additive_op`, `multiplicative_op`, `term`, `quality_ref`, `identifier`) | FR-001/FR-004 need left-fold repetition and a reference token; the old rules were right-recursive and had no identifier | Precedence climbing outside the PEG adds a second parsing technique; keeping right recursion keeps the wrong answers |
| New error types (`EvaluationError`, `ConstraintError`, `InvalidOperationError`) | A constraint on a string must fail clearly (spec edge case), and engine callers catch one base class | Reusing `InvalidQualityValueError` would misreport the failure as a bad stored value |
| `MemoryStorySource` next to `FileSystemStorySource` | FR-012 names both the compile layer and the application port | Only `MemoryLoader`: apps would hand-build `Environment` + `Story` and bypass the port |
