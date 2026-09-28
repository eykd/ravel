# ravel Constitution

<!--
Sync Impact Report:
- Version: 1.0.0 → 1.1.0 (MINOR - principle VII made mechanism-neutral:
  the core exposes immutable plain-data outputs and must not depend on a
  pub/sub library or module globals; blinker/signals are no longer mandated.
  Amended 2026-09-27 for feature 001-reentrant-vm, which removes blinker
  from the core.)
- Version: (none) → 1.0.0 (initial ravel constitution, ported from syml's
  constitution v2.0.0 by the spec-kit harness port)
- Ported and retargeted:
  - I (Test-Driven Development): unchanged in shape; `commit_red` now points
    at `tools/commit_red.py` as ported into this repo (`tools.commit_red`).
  - II (Type Safety): rewritten to describe ravel's ACTUAL mypy config
    (`files = ["src", "tools"]`, no strict-mode flags, `tests/` not
    type-checked) rather than copying syml's strict-mode claim, which is
    false for ravel.
  - III (Coverage and Lint Gates): rewritten for ravel's gate commands
    (`./runtests.sh`, `uv run ruff check`, `uv run ruff format --check`,
    `uv run pre-commit run --all-files`) and ravel's smaller ruff `select`
    set (no `D`/pydocstyle, no preview mode).
  - IV (Spec vs Implementation Discipline): retargeted at ravel's two specs,
    `docs/RAVEL_LANGUAGE_SPEC.md` and `docs/RAVEL_VM_SPEC.md`, in place of
    syml's single SYML-SPECIFICATION.md/SYML-SPEC-REVIEW.md decision record
    (which does not exist in this repo).
  - V (Simplicity / YAGNI): retargeted at ravel's own value proposition
    (a small QBN engine/VM) in place of syml's "every leaf is a plain str"
    claim, which does not hold for ravel's richer value types.
  - VI (Public API Stability): retargeted at ravel's actual public surface
    (`Environment.load()`, `Loader`, the compiled rulebook shape, `Source`/
    `Pos`, the VM's public event/signal surface) in place of
    `syml.loads`/`syml.load`.
- Added sections:
  - VII (Clean Architecture) — new for ravel: the domain core (compiled
    rulebook types in `types.py`, `queries.py`, the VM state machine in
    `vm/`) must not depend on I/O, CLI, or presentation; adapters (the CLI
    runner in `cli.py`, `ConsoleRunner`, file loaders in `loaders.py`)
    depend inward on the core, never the reverse.
- Removed sections: None (syml's decision-record citation machinery in
  principle IV has no ravel equivalent yet, so it is described as
  research.md-based instead of removed outright).
- Templates requiring updates: .specify/templates/plan-template.md (already
  retargeted to ravel's structure and specs during this port), .specify/
  templates/spec-template.md (no principle-specific wording present),
  .specify/templates/checklist-template.md (no principle-specific wording
  present)
- Follow-up TODOs: None
-->

## Preamble

This constitution governs development of `ravel`, a Python engine and
authoring language for Quality-Based Narratives (QBN). It exists to keep a
Parsimonious-PEG-grammar-driven compiler, a stack-based VM, and a
100%-branch-covered implementation from drifting into undisciplined
complexity as the specs (`docs/RAVEL_LANGUAGE_SPEC.md`,
`docs/RAVEL_VM_SPEC.md`) and the implementation converge.

---

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)

All implementation code MUST be preceded by a failing test. The cycle is
Red-Green-Refactor, entered via a Test List:

0. **Test List**: enumerate behavioral variants first (in beads, as leaf task
   titles — a planning artifact, **not** pre-written tests).
1. **Red**: write a failing test first, then commit it via
   `.venv/bin/python -m tools.commit_red <task-id>` before writing
   implementation code.
2. **Green**: write the minimal code to pass.
3. **Refactor**: improve the code while keeping tests green.

**Rationale**: A committed RED test is proof the test could fail before the
code existed, which is the only way to trust that a later green run means the
implementation — not the test — is correct.

### II. Type Safety

`uv run mypy` runs over `files = ["src", "tools"]` (per `pyproject.toml`);
`tests/` is **not** type-checked, and mypy is not run in strict mode —
`disallow_untyped_defs`/`disallow_any_generics`/`check_untyped_defs` are not
set, so most function bodies are unannotated by design and mypy skips them
unless a type error is otherwise surfaced. New code under `src/`/`tools/`
MUST still pass `uv run mypy` with zero errors; this is a "stay clean" gate,
not a "annotate everything" mandate.

**Rationale**: A small engine library benefits from precise types on its
public surface (`Source`, `Pos`, the compiled rulebook shape, VM events)
without paying the cost of full strict-mode annotation on every internal
helper and test.

### III. Coverage and Lint Gates

100% branch coverage is enforced by `./runtests.sh`
(`--cov=ravel --cov=tools --cov-branch`, backed by `fail_under = 100` in
`[tool.coverage.report]`), and CI runs pytest with branch coverage, `ruff
check`, and `ruff format --check` on every push and pull request. `ruff`'s
`select` set here is `["E", "F", "W", "B", "C4", "SIM", "I", "UP"]` — no
`D`/pydocstyle, no preview mode, no bandit `S`. Per `CLAUDE.md`, there are no
`# pragma: no cover` marks left in `src/` to imitate; a new one needs a
provable-unreachable justification, not a shortcut past an untested path.
`uv run pre-commit run --all-files` (ruff-check --fix, ruff-format, uv-lock,
and a local mypy hook) MUST pass before a commit lands.

**Rationale**: A grammar- and VM-driven engine has many structurally-required
branches that ordinary test-writing skips; the 100% gate forces every one of
them to be either exercised or explicitly justified as unreachable.

### IV. Spec vs Implementation Discipline

Any behavior change — in either direction — MUST cite the relevant section of
`docs/RAVEL_LANGUAGE_SPEC.md` (the authoring language: rulebook structure,
grammar, directives) or `docs/RAVEL_VM_SPEC.md` (VM/runner semantics: state
transitions, events, signals), or an FR-NNN requirement from the current
feature's plan. An open spec question MUST be settled — recorded as a dated
decision in the feature's `research.md` — before implementing against it,
except that a specification edit MAY land in the same commit as the behavior
change that exposed the question.

**Rationale**: Without this discipline, "fixing" a mismatch between spec and
implementation is a coin flip about which one was actually wrong; citing a
spec section or requirement makes every behavior change traceable to a
considered choice.

### V. Simplicity / YAGNI

The grammar stays line-oriented at the lexing level, composed from the
shared `base_expression_grammar` in `grammars.py` rather than growing
parallel ad hoc grammars. New compiled value types belong in `types.py`
alongside the existing `Text`/`Choice`/`Comparison`/`Operation` shapes, not
scattered across the compiler. No new runtime dependency may be added
without a plan-level justification in the Complexity Tracking section of
that feature's plan.

**Rationale**: ravel's value proposition is a QBN engine simple enough to
author `.ravel` files by hand and small enough to reason about end to end;
every added grammar dialect, value type, or dependency claws that back.

### VI. Public API Stability

`Environment.load()`/`Environment.load_rulebook()`, the `Loader` interface
(`BaseLoader.load`/`get_source`), the compiled rulebook shape (`{"rules":
[...], "locations": {...}}` per concept, plus flattened `metadata`/`givens`),
the semantics of `Source`/`Pos`, and the VM's public event surface
(`vm/events.py`, `vm/signals.py`, the `send_input` callable on
`waiting_for_input`) are the project's public API. A breaking change to any
of them MUST be listed explicitly in the plan's Constitution Check section,
with the alternative (non-breaking) approach it rejected.

**Rationale**: This project is an engine other code (a `Runner`, a game, a
tool) is built against; silent signature or semantics drift breaks callers
who pinned a version in good faith.

### VII. Clean Architecture

The domain core — the compiled rulebook types (`types.py`), the query/scoring
logic (`queries.py`), and the VM state machine (`vm/machines.py`,
`vm/states.py`, `vm/events.py`) — MUST NOT import from or depend on I/O, the
CLI, or presentation concerns. Adapters — the CLI (`cli.py`), `ConsoleRunner`
and other `vm/runners.py` runners, and the file-based loaders
(`loaders.py`'s `FileSystemLoader`) — depend inward on the core; the core
never imports them. Everything the VM's core exposes outward does so through
immutable output values holding only plain data (no live state objects, no
callables), never by a runner reaching into VM internals directly. The
delivery mechanism (returned values, a pub/sub library, etc.) is an adapter
choice; the core MUST NOT depend on a pub/sub library or module-level global
state.

**Rationale**: Keeping the compiler and VM's core free of I/O and
presentation dependencies is what lets a new `Runner` (a web frontend, a
test harness, a different console UI) be built against the same core without
forking or monkeypatching it, and is what keeps the core unit-testable
without mocking a terminal or filesystem.

---

## Governance

### Amendment Procedure

1. Propose the amendment with clear rationale.
2. Identify affected templates (`.specify/templates/*`) and code.
3. Create a migration plan for existing code if the amendment changes
   established behavior.
4. Update this constitution with a version bump.
5. Propagate changes to all dependent templates.
6. Update `CLAUDE.md` if runtime guidance to Claude Code is affected.
7. Commit with message: `docs: amend constitution to vX.Y.Z (summary)`.

### Versioning Policy

This constitution follows semantic versioning:

- **MAJOR**: Backward-incompatible principle removals or redefinitions.
- **MINOR**: A new principle or section added, or materially expanded
  guidance.
- **PATCH**: Clarifications, wording, typo fixes, non-semantic refinements.

### Compliance Review

- This constitution supersedes all other practices and documentation.
- Every plan MUST pass the Constitution Check gate before Phase 0 research,
  re-checked after Phase 1 design.
- Any complexity introduced MUST be justified in Complexity Tracking.
- Violations require either a fix or a constitutional amendment — never a
  silent exception.
- Use `CLAUDE.md` for day-to-day runtime guidance to Claude Code.

**Version**: 1.1.0 | **Ratified**: 2026-09-27 | **Last Amended**: 2026-09-27
