---
date: 2026-09-28
topic: spec-compliance
---

# Ravel Spec Compliance

## Problem Frame

An audit on 2026-09-28 found that the implementation falls short of `docs/RAVEL_LANGUAGE_SPEC.md` in
core expression and effect semantics. It also found that `docs/RAVEL_VM_SPEC.md` mostly describes a
deferred instruction-set design instead of the shipped engine. Each gap was confirmed by running the
parser and evaluator directly:

- `min`/`max` constraints parse but are never applied.
- `value` raises `TypeError`, because it compiles to a bare class.
- Quality references in expressions don't work. `Health` is a parse error, and `[Health]` and
  `"Health"` come back as string literals.
- Arithmetic is right-associative (`10 - 4 - 2` gives 8), and `*` binds looser than `/`, `//` and `%`.
- Negative literals and `""` don't parse.
- A concept line without a `when:` after it becomes intro text.
- VM spec §0 wrongly marks Expression and Constraint as "Implemented".

Authors writing `.ravel` files from the spec get parse errors or silently wrong arithmetic. Apps
embedding the engine have no accurate VM document to build against.

**David's direction (2026-09-28):** the goal is a fully working Ravel language as specified. The VM
must be deterministic, have savable state, implement the whole language, and stay I/O-free, so it
can drop into any application (realtime, async or HATEOAS). It should keep a clean hexagonal (ports
and adapters) shape. The VM needn't match its spec's details if it keeps the spirit, and the VM spec
gets rewritten to match the engine. Rewrite as little of either as possible. **When in doubt, favor
working, tested, well-architected code over the spec.**

## Requirements

**Expressions**

- R1. Arithmetic is left-associative. `*`, `/`, `//` and `%` share one precedence tier, above `+`
  and `-`. `10 - 4 - 2` gives 4, and `8 / 4 / 2` gives 1.
- R2. Negative integer and float literals parse (`X = -5`, `Health > -1`), and binary minus still
  works (`X = 10 - 4`).
- R3. The empty string `""` parses as a string literal.
- R4. An identifier (`[A-Za-z_]\w*`) or a `[Bracketed Name]` in an expression reads that quality's
  current value, or 0 if it's unset. A quoted token in an expression is always a string (ruling R3
  below).
- R5. `value` in an operation's or comparison's expression evaluates to the subject quality's current
  value. `X += value * 2` on 10 gives 30.

**Effects**

- R6. `min`/`max` constraints clamp an operation's result. `X -= 10 min 0` on 5 gives 0. This holds
  for operations in situations and for `given` values.

**Compiler and loader**

- R7. A rule's first item is a concept declaration if a `when:` follows it, or if it exactly names a
  registered concept handler. Otherwise it's intro text (ruling R6).
- R8. Include cycles are allowed. Each rulebook loads once, in breadth-first order (ruling R1).
- R9. `text:` inside a `choice:` compiles and plays as the spec describes. Add a test that pins it.

**Embeddability (hexagonal)**

- R10. An app can compile and play a story from in-memory strings, without touching the filesystem.
- R11. `Environment` takes its loader as an injected dependency and does not default to the
  filesystem adapter.
- R12. The engine supports a stateless request/response (HATEOAS-style) cycle. Save to bytes, resume
  from the bytes, choose, and save again, with no session object held between requests.
- R13. The engine is deterministic: the same story and the same choices give identical outputs and
  state.
- R14. Save round-trips preserve every value kind the language can produce, including negatives,
  floats and `""`.

**Documentation**

- R15. Language spec v0.2 applies rulings R1–R8 below. It adds a precedence and associativity table,
  and resyncs its PEG listing (§10.1) and Cloak listing (§12) with the code.
- R16. VM spec v0.2 describes the shipped engine. That covers the domain model; the
  `start`/`choose`/`present`/`resume` API; the seven output types; the determinism and save
  guarantees; the ports and adapters; and recipes for realtime, async and HATEOAS hosts built on the
  pure API. The instruction-set body shrinks to a short design-history appendix.
- R17. The CLAUDE.md "Language reference" paragraph matches the new docs.
- R18. Every expression, comparison and operation example in the language spec (§4–§7, §9, §11.4)
  runs as a test, so the spec can't drift from the code again.

## Spec-Contradiction Rulings (decided; favor code)

| # | Contradiction | Ruling |
|---|---|---|
| R1 | §3.1 forbids circular includes, but `examples/cloak` has them | Cycles allowed; each rulebook loads once, breadth-first. Fix the spec. |
| R2 | §3.1 claims include order affects rule order and "later includes take precedence" | Drop both claims. The spec states the real ordering (score, then location descending). For `given`, later-loaded values win. |
| R3 | §5.2 calls `"Wearing Cloak"` a quality reference; §4.2/§10.1 make it a string | In expressions, a quoted token is always a string. Quality refs are identifiers or `[Bracketed Name]`. Quoted names stay valid as a comparison's or operation's subject. |
| R4 | §4.1 "no reserved words" vs Appendix A reserving `value`, `min` and `max` | Reserved inside expressions only; still valid as subject names. |
| R5 | §9.1 example output contradicts the stated `[.]` rule | The rule wins; fix the example. |
| R6 | §8.1 concept line is optional but ambiguous with one-word intro text | See R7 above. Document it. |
| R7 | Can the first line use `{cond}`/`<>`? | No. The first line uses intro syntax only. Document it; no code change. |
| R8 | Whitespace around operators is unspecified | Required around setters and comparators, optional around arithmetic operators. Document it. |

## Success Criteria

- Every construct in the language spec compiles and behaves as documented, with a test.
- The VM spec describes the shipped engine and its ports; nothing in it is aspirational without a
  "deferred" label.
- The probe regressions above pass as tests.
- `uv run ravel run examples/cloak` plays through to both endings.
- The full gate stays green: `./runtests.sh` at 100% branch coverage, ruff, mypy and pre-commit.

## Scope Boundaries

- No new language features beyond what the spec already documents.
- No instruction-set VM, JSON IR or alternate execution modes. Those stay in design history.
- No realtime, async or HATEOAS host adapters ship. The VM spec documents recipes, and one
  acceptance test proves the HATEOAS cycle.
- Save format stays at version 1, unless the new value kinds force a change. If so, planning records
  why.

## Key Decisions

- Favor working, tested, well-architected code over the spec, then fix the spec to match.
- Rewrite the VM spec to match the engine, not the reverse.
- Spec examples become tests (R18), so drift fails the build.

## Dependencies / Assumptions

- Builds on the landed 001-reentrant-vm (engine, save format v1, `GameSession`, ports and adapters).
- `hypothesis` is already a dev dependency, so R13 adds no new dependency.

## Outstanding Questions

### Deferred to Planning

- [Affects R11][Technical] Dropping `Environment`'s default loader breaks `Environment()` callers.
  That's a Principle VI public-API change, so the plan's Constitution Check must list it with the
  rejected non-breaking alternative.
- [Affects R1–R5][Technical] The grammar rewrite must keep regex backslashes doubled and keep
  `tests/test_grammars.py` passing. Make that an explicit acceptance criterion for grammar tasks.
- [Affects R14][Technical] Confirm that save format v1 already encodes negatives, floats and `""`
  losslessly.
- [Affects R4][Technical] Decide how a bracketed name in an expression is told apart from the
  `[bracketed]` intro-text syntax, if the two grammars ever meet.

## Next Steps

-> `/sp:02-specify` to create the formal specification
