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
- No typed errors for arithmetic failures other than constraints (`1 / 0`, `"a" + 1`); filed as a
  follow-up (PD-08).

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
| `ravel.engine` errors | `start`/`choose` can raise the new `InvalidOperationError(EngineError)` | Let `ConstraintError` escape unwrapped: engine callers would need a second `except`. |

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
| Quality refs (FR-004, R3) | §4.1, §5.2, §10.1 | Yes: identifiers and `[Bracketed]` in expressions; quoted tokens are strings; `[Has-Key]` for punctuated names |
| Quoted tokens are strings (FR-005, R3) | §5.2 | Yes: replace `"Wearing Cloak"` with `[Wearing Cloak]` in the term list |
| `value` (FR-006) | §4.3 | Only a sentence: `value` is 0 for an unset subject; works in comparisons too |
| Reserved words (FR-007, R4) | §4.1, Appendix A | Yes: "no reserved words in subject position" |
| Constraints (FR-008) | §7.3, §10.1 | Yes: one per operation; applies to `=` and `given`; string result is an error; clamped value takes the bound's kind |
| Concept line (FR-009, R6) | §8.1, §8.2 | Yes: the detection rule and its one-word-intro trade-off |
| Include cycles, ordering (FR-010, R1, R2) | §3.1, §3.2 | Yes: cycles allowed, BFS, real ordering, later `given` wins |
| `text:` in `choice:` (FR-011) | §9.2 | No: "(optional additional text)" already matches (PD-10) |
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
├── test_types.py            # evaluation, constraints
├── test_queries.py          # references in predicates
├── test_compiler_rulebooks.py   # concept detection
├── test_environment.py      # required loader, cycles
├── test_loader.py           # MemoryLoader
├── spec_examples.py         # new helper: extract_examples / run_example (PD-16)
├── test_spec_examples.py    # new (PD-16)
├── conftest.py              # Environment() callers pass a loader
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
| US1: expressions | `tests/acceptance/spec_compliance/test_us01_expressions.py` | parsers + `evaluate`; a one-file story through `engine.start` for AS5/AS7 | 8 |
| US2: constraints | `tests/acceptance/spec_compliance/test_us02_constraints.py` | situation effect via `engine.choose`; `given` via `engine.start` | 4 |
| US3: rulebooks | `tests/acceptance/spec_compliance/test_us03_rulebooks.py` | `Environment(MemoryLoader)`; counting loader for AS3; engine for AS4 | 4 |
| US4: embedding | `tests/acceptance/spec_compliance/test_us04_embedding.py` (AS1, AS2, AS3, AS5), `test_us04_determinism_property.py` (AS4; hypothesis, `max_examples=200`, `deadline=None`, `derandomize=True`, `database=None`) | `MemoryStorySource`, filesystem calls patched to raise; stateless handler | 5 |
| US5: docs | `tests/acceptance/spec_compliance/test_us05_docs.py` | reads both docs and `CLAUDE.md`: versions are 0.2; §5.1 has the precedence table; each ruling's key sentence is present; §12 shows **all five** `examples/cloak/*.ravel` files and each listing equals its file's text (today it shows three, and its `begin.ravel` is out of date); VM spec names `start`/`choose`/`present`/`resume`, all seven output types, the three host recipes, and has a design-history appendix | 3 |
| US6: spec can't drift | `tests/acceptance/spec_compliance/test_us06_spec_examples.py` | runs the extractor over the real spec (AS1) and over a copy with one result edited (AS2), asserting the failure names the example | 2 |

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

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| New grammar rules (`additive_op`, `multiplicative_op`, `term`, `quality_ref`, `identifier`) | FR-001/FR-004 need left-fold repetition and a reference token; the old rules were right-recursive and had no identifier | Precedence climbing outside the PEG adds a second parsing technique; keeping right recursion keeps the wrong answers |
| New error types (`EvaluationError`, `ConstraintError`, `InvalidOperationError`) | A constraint on a string must fail clearly (spec edge case), and engine callers catch one base class | Reusing `InvalidQualityValueError` would misreport the failure as a bad stored value |
| `MemoryStorySource` next to `FileSystemStorySource` | FR-012 names both the compile layer and the application port | Only `MemoryLoader`: apps would hand-build `Environment` + `Story` and bypass the port |
