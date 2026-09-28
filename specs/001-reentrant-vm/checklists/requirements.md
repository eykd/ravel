# Specification Quality Checklist: Re-entrant VM with Save/Load and a Winnable Cloak of Darkness

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - *Justified exception:* the feature is an architectural rewrite requested as such. The spec
    names:
    - the three layers;
    - the save-file fields and the canonical JSON form (a user-visible file format);
    - `check_untyped_defs`;
    - Hypothesis (explicitly requested as the property-test tool).

    It does not name classes, modules, or algorithms. Instruction encoding, the identity-hash
    derivation, and blinker's fate in the CLI are deferred to planning.
- [x] Focused on user value and business needs
  - Every story is framed for a player, an author, or an engine user. The principal's goal
    (play, save, load, win) maps to US3, US4, US5, and US6.
- [x] Written for non-technical stakeholders
  - *Partial by nature:* the stakeholder is the maintainer-principal, an engineer. The user
    stories and the user-facing success criteria read without code knowledge. The FRs are
    technical because the request is.
- [x] All mandatory sections completed
  - User Scenarios & Testing, Requirements, and Success Criteria are all filled. Edge Cases, Key
    Entities, Assumptions, Clarifications, and "Decided while you slept" are included.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
  - Every open point became a recorded decision (Clarifications, "Decided while you slept") or a
    planning-deferred assumption.
- [x] Requirements are testable and unambiguous
  - Each FR names an observable behaviour. The menu order, the default save path, the exit
    codes, and the refusal conditions are all stated concretely.
- [x] Success criteria are measurable
  - Examples: the 12-choice win route, the `won`/`lost` outcomes, ≥200 property examples at 100%
    agreement, 100% branch coverage, and a zero-import rule for the domain.
- [x] Success criteria are technology-agnostic (no implementation details)
  - SC-001 to SC-006 are user-facing and tool-free.
  - *Justified exception:* SC-007 to SC-009 are engineering gates, labelled as such, because the
    principal asked for coverage, typing, and architecture as deliverables.
- [x] All acceptance scenarios are defined
  - Each of US1 to US6 has Given/When/Then scenarios and an independent test.
- [x] Edge cases are identified
  - Covered:
    - a corrupt save;
    - a story changed since the save;
    - an unknown format version;
    - an unknown location;
    - choosing a location that isn't offered;
    - choosing after a halt;
    - choosing while running;
    - a dead end;
    - `+=` givens;
    - mid-session file edits;
    - directives after `end`;
    - two sessions in one process.
- [x] Scope is clearly bounded
  - The deferred list is in Assumptions and in the brainstorm's Scope Boundaries.
- [x] Dependencies and assumptions identified
  - These are syml 1.0's availability, the Python floor, the planning-deferred technical
    choices, and the MAJOR constitution amendment to Principles VI and VII.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
  - FR-001 to FR-004 map to US1.
  - FR-005 to FR-016 map to US2 (with the FR-033 fixture covering FR-009, FR-012, and FR-014).
  - FR-017 to FR-020 map to US3.
  - FR-021 to FR-025 map to US4.
  - FR-026 to FR-030 map to US5.
  - FR-031 to FR-033 map to US6.
  - FR-034 to FR-039 are checked by SC-007, SC-008, and the doc review.
- [x] User scenarios cover primary flows
  - The flows covered are: new game, in-situation choice with a gather, query menus, win, loss,
    dead end, save, load, `--load`, quit, and verbose/debug.
- [x] Feature meets measurable outcomes defined in Success Criteria
  - Each SC traces to at least one story: SC-001 and SC-002 to US3 and US6, SC-003 to US4 and
    US6, SC-004 to US2 and US5, SC-005 to US5, SC-006 to US4 and US5, SC-007 and SC-008 to the
    architecture FRs, and SC-009 to US1.
- [x] No implementation details leak into specification
  - This carries the same justified exception as the first Content Quality item. The layering
    and the save format are the subject of the feature. Nothing below that level is specified.

## Notes

- Validation passed on the first iteration, with the two justified exceptions noted above.
- `/sp:02-specify` steps that were deliberately skipped, per the caller's instructions: the
  interview, the branch script (the branch already existed), the beads epic and phase tasks, the
  `specs/readme.md` pin, and glossary updates (`docs/glossary.md` does not exist).
- Items for the principal to review are listed in the brainstorm's "For David to review". The
  `end` directive syntax comes first.
- Next step: `/sp:03-plan`. The plan's Constitution Check must record the Principle VI/VII break
  and the proposed amendment.
