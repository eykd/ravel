# Research: Ravel Spec Compliance (002)

**Date**: 2026-09-28 · **Spec**: [spec.md](spec.md) · **Brainstorm**:
[2026-09-28-spec-compliance-requirements.md](../brainstorms/2026-09-28-spec-compliance-requirements.md)

Every decision below is dated and named, per Constitution Principle IV. The governing rule, from
David on 2026-09-28: **favor working, tested, well-architected code over the spec, and rewrite as
little of either document as possible.** Rulings R1–R8 were decided before planning; they are
recorded here verbatim so the spec edits in FR-017 can cite them. Planning decisions are `PD-NN`.

Probes run on 2026-09-28 against `main` @ `4f54687` (scripts kept in the session scratchpad, not the
repo). Their results are quoted where they settle a question.

---

## Spec-contradiction rulings (decided 2026-09-28, David)

### R1. Include cycles are allowed

- **Decision**: An include cycle loads. Each rulebook is compiled once, in breadth-first order from
  `begin`. Language spec §3.1's "Circular includes are not permitted" is deleted.
- **Rationale**: `examples/cloak` already has cycles (`begin → foyer → cloakroom → foyer`, and
  `bar-dark`/`bar-light` include `foyer`). `Environment.load_rulebook` already dedupes through its
  `loaded_rulebooks` map, so the code is right and the spec is wrong.
- **Alternatives**: forbid cycles and rewrite Cloak (breaks the flagship example for no gain).

### R2. Include order doesn't order rules; later `given` values win

- **Decision**: Drop §3.1's "Include order matters for rule ordering" and "rules from later includes
  taking precedence". State the real ordering: rules sort by score (predicate count) descending,
  then by location descending (`queries.query` sorts `(score, name, …)` with `reverse=True`). For
  `given`, operations run in load order, so a later-loaded rulebook's value for the same quality
  wins. Same-named locations can't collide across files, because names are namespaced
  `file::rule`.
- **Alternatives**: make include order meaningful (a new feature, out of scope).

### R3. A quoted token in an expression is a string

- **Decision**: Inside an expression, `"…"` (and every other quote style) is always a string
  literal. Quality references are identifiers or `[Bracketed Name]`. Quoted names stay valid as the
  *subject* of a comparison or operation. §5.2's `"Wearing Cloak"` example moves to `[Wearing
  Cloak]`.
- **Rationale**: §4.2 and §10.1 already say so, and Cloak depends on `Location = "Foyer"` meaning
  the string `Foyer`.

### R4. `value`, `min` and `max` are reserved inside expressions only

- **Decision**: They can't be quality references inside an expression. They stay valid as subject
  names (`value = 3` parses today and keeps parsing). §4.1's "No reserved words" becomes "No
  reserved words in subject position; see Appendix A for expressions."

### R5. §9.1's `[.]` example is wrong; the rule wins

- **Decision**: `You enter the bar[.]` gives intro `You enter the bar.` and tail
  `You enter the bar` (head + tail, tail empty). Fix the example's comment.

### R6. The concept line is detected by `when:` or by a registered name

- **Decision**: See PD-09. A rule's first item is a concept declaration if a `when:` follows it or
  if it exactly names a registered concept handler. Otherwise it's intro text. Document it in §8.1.

### R7. A rule's first line uses intro syntax only

- **Decision**: No `{cond}` prefix and no `<>` glue on a rule's or choice's first line. Document in
  §9.1. No code change: `IntroTextParser` has no such rules today.

### R8. Whitespace

- **Decision**: Required around setters (`=`, `+=` …) and comparators; optional around arithmetic
  operators. Document in §6.2 and §7.2. Probe confirms the code already does this: `X=5` and `X>1`
  are rejected, `X = 10-4` parses.

---

## Planning decisions (2026-09-28)

### PD-01. Left-associative arithmetic via repetition and a left fold

- **Decision**: Replace the three right-recursive rules (`additive`, `multiplicative`, `divisive`)
  with two repetition rules, the shape §10.1 already shows:

  ```peg
  expression     = additive
  additive       = multiplicative (ws? additive_op ws? multiplicative)*
  multiplicative = primary (ws? multiplicative_op ws? primary)*
  additive_op    = add / subtract
  multiplicative_op = multiply / floor_div / divide / modulus
  primary        = term / (open_paren ws? expression ws? close_paren)
  ```

  The visitor folds each rule's children left: `a - b - c` → `Expression(Expression(a,-,b),-,c)`.
  A single operand passes through unwrapped, so `X = 5` still compiles to the bare `5`.
  `floor_div` stays ahead of `divide` in the ordered choice so `//` isn't read as two `/`.
- **Rationale**: Probe: `10 - 4 - 2` gives 8 and `2 + 3 * 4` builds `2 + (3 * 4)` only by accident
  of right recursion; `*` sat on its own tier above `/`. Repetition plus a fold is the standard PEG
  fix, and it keeps one shared `base_expression_grammar` (Principle V).
- **Alternatives**: left recursion (parsimonious doesn't support it); a precedence-climbing parser
  outside the PEG (a second parsing technique for one rule).
- **Expected test edits**: `tests/test_parsers.py::TestOperationsParser::test_it_should_handle_a_more_complicated_expressions`
  and `::test_it_should_handle_a_complex_expression` assert today's right-nested trees. They change
  to left-nested trees. That's the bug being fixed, not a regression.

### PD-02. Signed number literals; `10 -4` is binary

- **Decision**: `integer = ~"-?\\d+"`, `float = ~"-?\\d+\\.\\d*"` (today's float shape plus a sign).
  Only literals take a sign; there's no unary minus on references or groups (`-Health`, `-(1+2)`
  stay parse errors, and the spec says so).
- **Rationale**: Inside `additive`'s repetition, PEG tries `ws? subtract ws? multiplicative` before
  a new operand, so `10 -4` and `10-4` both read as subtraction (6). A `-` that can't be an operator
  (after `=`, after another operator, or after `(`) starts a negative literal, so `10 - -4` is 14
  and `X = -5` is -5. The constraint bound uses the same `number` rule, so `min -5` works too.
- **Alternatives**: a unary-minus operator (new language feature; not in the spec).

### PD-03. Empty strings

- **Decision**: Every quote style's body regex goes from `+` to `*` (`~'[^"]*'`, etc.). The
  triple-quote forms stay ahead of the single-quote forms in the ordered choice, so `""` is an empty
  double-quoted string and `""""""` is an empty triple-quoted one.
- **Visitor note**: `visit_string` reads `node.children[0].children[1].text`, which is `""` for an
  empty body. No visitor change beyond keeping that path.

### PD-04. Quality references: identifiers and bracketed names

- **Decision**: Add `quality_ref = bracketed_quality / identifier` to `term`, with
  `identifier = ~"(?!(?:value|min|max)\\b)[^\\W\\d]\\w*"`. Both compile to a new
  `types.QualityRef(name)`. The subject rule (`quality`) is unchanged, so subjects keep accepting
  `[^\s]+`, quoted and bracketed names.
- **Term order**: `term = number / string / qvalue / quality_ref`. `qvalue` is `~"value\\b"` (not
  the bare literal `"value"`, which today would match the start of `values`).
- **Reserved words (R4)**: the negative lookahead keeps `value`, `min` and `max` out of identifier
  position. `maxHealth` and `values` are still identifiers, because `\b` requires a word boundary.
- **Identifier alphabet**: a Unicode letter or `_`, then Unicode word characters. The brainstorm
  sketched `[A-Za-z_]\w*`; `[^\W\d]` is the same rule extended to non-ASCII initials, so a quality
  named `Été` is referenceable. Subject names that contain `-` or other punctuation are referenced
  with brackets (`[Has-Key]`); `X = Has-Key` parses as `Has - Key`. The spec says so in §5.2.
- **Unset reads 0**: `QualityRef.evaluate` returns the quality's value, or `0` when it's unset
  (FR-004; §4.2's "defaults to 0").
- **Semantics change**: today `X == [Y]` compiles to the *string* `"Y"` (probe:
  `('X' == 'Y')`), because `visit_bracketed_quality` strips the brackets and returns text. Under
  FR-004 it reads quality `Y`. No shipped story or fixture uses a bracketed name on an expression's
  right-hand side (grep of `examples/` and `tests/fixtures/`), so nothing in-repo changes behavior.
  Listed in plan.md's Constitution Check.

### PD-05. Bracketed names never meet `[bracketed]` intro text (deferred item 4)

- **Decision**: No grammar change is needed to tell them apart. Record the reason in §9.1.
- **Rationale**: The two grammars are separate `Grammar` objects that never compose.
  `IntroTextParser` only ever sees a situation's or choice's first item
  (`compile_directives`/`compile_choice`), and R7 forbids a `{cond}` prefix there, so no
  expression can appear on an intro line. Expressions only appear in `given:`/`effect:` operations,
  `when:` comparisons and a plain-text line's `{…}` prefix. Inside a prefix, a `[Name]` belongs to
  the comparison; brackets in the text after `}` are plain text. Probe:
  `{X > 1} some [bracket] text` → text ` some [bracket] text`.
- **Known quirk, out of scope**: `bracketed_quality = ~'\[[^\]]+\]'` will swallow a `}`, so
  `{X == [a} b]} text` parses with the name `a} b`. That's pre-existing, harmless, and needs a
  pathological name to trigger. Not changed.

### PD-06. `value` and the evaluation context

- **Decision**: Evaluation takes one keyword context everywhere:
  `evaluate(*, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0)`, where `QualityLookup` is any
  object with `.get(name) -> QualityValue | None` (both `engine.state.Qualities` and a plain
  `dict` qualify). `types.VALUE` becomes a singleton *instance* of a new `Value` class whose
  `evaluate` returns `qvalue`. `Operation.evaluate(initial_value, *, qualities=EMPTY_QUALITIES)` passes
  `qvalue=initial_value`; `Comparison.evaluate(qvalue, *, qualities=EMPTY_QUALITIES)` passes its
  subject's value. Every `qualities` defaults to an empty read-only mapping, so existing calls with
  no context (`exp.evaluate()`, `operation.evaluate(None)`, `comparison.evaluate(2)` in
  `tests/test_types.py`) keep working unchanged.
- **Root cause of the audit's `TypeError`**: `visit_qvalue` returns the *class* `types.VALUE`,
  `evaluate_term` sees no `evaluate` on it, and the class reaches `op.mul`. Nothing ever passed a
  subject value to an `Expression` inside an operation.
- **Keeping `VALUE` as a name**: existing tests compare trees against `types.VALUE`. A singleton
  instance keeps those comparisons working (attrs `eq`), so the fix doesn't churn them.
- **Threading qualities into predicates**: `queries.query_predicates` calls `predicate(qvalue)`
  with no qualities, and `_Run.query` passes `self.qualities.items` (a tuple of pairs). Under
  FR-004, `when: X > Y` needs `Y`. `query_predicates` builds one `dict(query)` and passes it as
  `qualities=`; `Text.check`/`Predicate.check`/`Comparison.check` forward `qualities` to
  `evaluate`.
- **The `except TypeError` fallback**: for an unset subject, `query_predicates` calls
  `predicate(0)` and treats a `TypeError` as "no match" (e.g. `Location = "Bar"` is fine, but
  `Location > "Bar"` against 0 raises). That stays as-is for comparator type mismatches. It must
  not start swallowing new failures, so quality-reference evaluation raises nothing new: an unset
  reference reads 0 and a set one returns its value.
  **Amended by red-team pass 1 (2026-09-28)**: that premise fails for arithmetic on a reference
  (`X > 10 / Y`, Y unset). Both branches now treat `TypeError`, `ArithmeticError` and
  `EvaluationError` as a non-match, logged at `WARNING`, so no save can be stranded by a raising
  predicate (plan.md RT-2).

### PD-07. `value` outside an operation or comparison (deferred item 5)

- **Decision**: Unreachable by grammar, so no error path is built. Record it.
- **Rationale**: `expression` is only entered from `operation` and `comparison` (and a `{…}`
  prefix, which is a comparison). `value` inside a `given:` operation reads that subject's current
  value (0 if unset, or an earlier `given`'s value). The one other slot is a constraint bound, which
  is a `number` literal, so `X += 1 max value` is a parse error today and stays one.
- The spec's edge case ("a compile error, not a runtime crash") is met: every place `value` can be
  written either parses with a subject or fails to parse.

### PD-08. Constraints clamp in `Operation.evaluate`; non-numeric results raise

- **Decision**: `Operation.evaluate` computes `operator(initial, expression)`, then applies the
  constraint: `min` → `max(result, bound)`, `max` → `min(result, bound)`. It applies to every
  setter, `=` included, and to `given` (which runs through the same `_apply_operation`). At most one
  constraint per operation, bound a signed number literal; `X += 1 min 0 max 8` stays a parse error
  (stacking bounds is a new feature).
- **Non-numeric result**: a constraint on a `str` result raises
  `ravel.exceptions.ConstraintError` (new; subclass of a new `ravel.exceptions.EvaluationError`,
  itself a `ValueError`). It's a runtime check, because once quality references exist the result
  type isn't known at compile time (`X = Name max 3`).
- **Also at compile time**: when the expression is a bare string *literal* (`X = "a" max 3`, which
  parses today), `OperationParser.visit_operation` raises `OperationParseError` naming the text.
  That's the cheap, certain case; the runtime check covers the rest.
- **Engine boundary**: `_apply_operation` (the one choke point every quality change passes through)
  catches `EvaluationError` and re-raises it as a new
  `ravel.engine.errors.InvalidOperationError(EngineError)`, chaining the cause. Engine callers keep
  catching one base class, and `GameSession`'s "an `EngineError` leaves state untouched" still
  holds, since the run's scratch state is discarded.
- **Import cycle**: `ravel.exceptions` imports `Source` from `ravel.types` today, so `types.py`
  can't import `ravel.exceptions`. `exceptions.py` switches to `from syml.basetypes import Source`
  (the same class `types` re-exports), which breaks the cycle. `types.py` then imports
  `ravel.exceptions.ConstraintError`.
- **Bound kind**: the clamped value takes the bound's value *and kind*. `X = 5; X -= 10 min 0.0`
  gives `0.0`. Documented in §7.3.
- **Out of scope**: other arithmetic failures (`"a" + 1`, `1 / 0`) still raise Python's
  `TypeError`/`ZeroDivisionError` from inside the engine. No spec text covers them; changing them
  would also change what the unset-quality `TypeError` fallback in PD-06 catches. Filed as a
  follow-up, not fixed here.
- **Amended by red-team pass 1 (2026-09-28)**: quality references make `1 / 0` and `"a" + 1`
  reachable from ordinary story text (`X = 100 / Bonus` with Bonus unset). No new error type, but
  `_apply_operation` now also wraps `ArithmeticError` and `TypeError` in `InvalidOperationError`,
  and predicates treat those failures as non-matches. See plan.md, Edge Cases & Error Handling
  (RT-1, RT-2). Unbounded string growth (`X *= 2` on a string) stays a follow-up.

### PD-09. Concept detection (FR-009, R6)

- **Decision**: `compile_rulebook` gains a middle branch. In order:
  1. `data[0]` is a `when:` → Situation, predicates from it.
  2. `data[1]` is a `when:` → concept `data[0]`, predicates from `data[1]`.
  3. **New**: `data[0]` is text and `concepts.is_registered(get_text(data[0]).strip())` → concept
     `data[0]`, no rule predicates, baggage `data[1:]`.
  4. Otherwise → Situation, no predicates, baggage `data[:]` (the first item is intro text).
- `concepts.is_registered(name) -> bool` is new and public (reads `_HANDLERS`), so the compiler
  doesn't reach into a private dict.
- **Trade-off, documented in §8.1**: a one-word intro line that exactly matches a registered concept
  (`Situation`) is read as the concept. Only `Situation` is registered out of the box. Custom
  concepts handled by `_dummy_handler` aren't registered, so they still need a `when:` to be
  recognized.

### PD-10. `text:` inside `choice:` is additional text (FR-011)

- **Decision**: Pin the shipped behavior. No code change.
- **Probe**: a choice `[Go]You go.` with `text: Extra words.` offers `Go`, and taking it shows
  `You go.` then `Extra words.`, then the choice's effects. The menu label isn't changed. That's
  what §9.2 already calls "(optional additional text)". US3-AS4 was reworded to say the same
  (`583eb86`); the test asserts the exact output sequence in contracts/rulebook-compile.md.

### PD-11. In-memory story sources (FR-012)

- **Decision**: Two small adapters, one per layer the spec names:
  - `ravel.loaders.MemoryLoader(sources: Mapping[str, str])`, a `BaseLoader` whose `get_source`
    returns `(sources[name], always_true)` and raises `RulebookNotFound(name)` for a missing name.
    It copies the mapping on construction so later edits to the caller's dict can't change a
    compiled story mid-cache.
  - `ravel.adapters.story_source.MemoryStorySource(sources, *, entry="begin")`, a `StorySource`
    that compiles through `Environment(loader=MemoryLoader(sources), initializing_name=entry)`.
- **Rationale**: `Environment` is the compile layer and `StorySource` is the application port;
  FR-012 asks for both. Neither touches the filesystem. `MemoryLoader` has no I/O, so it can sit in
  `loaders.py` next to `BaseLoader`.
- **Proof of zero filesystem reads (SC-003)**: the acceptance test monkeypatches `builtins.open`,
  `pathlib.Path.open`, `os.stat` and `os.path.getmtime` to raise, then compiles and plays a story
  from strings.

### PD-12. `Environment` requires its loader (FR-013)

- **Decision**: `loader = attr.ib()` with no default, plus a validator that it has a callable
  `load`. `environments.py` stops importing `ravel.loaders`. `Environment()` raises `TypeError`
  (attrs: "missing 1 required positional argument: 'loader'"); `Environment(loader=object())`
  raises `TypeError` naming the missing `load`.
- **Rejected non-breaking alternatives**:
  - *Keep `FileSystemLoader()` as the default, with a `DeprecationWarning`.* The core would still
    import the filesystem adapter, and a forgotten argument would still read the working directory
    silently. That silent read is the exact failure FR-013 bans.
  - *Default to an empty `MemoryLoader({})`.* Non-breaking at construction, but `load()` then fails
    later with a confusing `RulebookNotFound('begin')` far from the mistake.
- **Callers to update** (all in-repo): `tests/conftest.py:18`, `tests/conftest.py:23`,
  `tests/test_queries.py:67`, `tests/test_compiler_concepts.py:29`, `tests/test_environment.py:10`.
  Every `src/` caller (`FileSystemStorySource`) already passes `loader=`.
- **Listed as a Principle VI break** in plan.md.

### PD-13. Stateless request/response and determinism (FR-014, FR-015)

- **Decision**: Test-only. No engine change.
- **HATEOAS cycle (US4-AS3)**: a handler function takes `(story, save_bytes, location)` and does
  `decode_save` → `engine.resume` → `engine.choose` → `encode_save`. The test calls it twice in a
  row, holding only bytes between calls, and asserts that `resume(decode(new_bytes)).state` equals
  the state the handler computed and that `encode_save` of it reproduces `new_bytes` exactly.
- **Determinism (US4-AS4)**: hypothesis, same settings as 001's PD-16 (`max_examples=200`,
  `deadline=None`, `derandomize=True`, `database=None`). Strategy: a list of choice indices taken
  modulo the menu size, stop at halt. Play the same path twice on the same `Story` and on a freshly
  compiled `Story`, and assert equal output tuples, equal final `GameState`s, and equal save bytes.

### PD-14. Save format v1 already round-trips every new value kind (deferred item 3; FR-016)

- **Decision**: The save format stays at version 1. FR-016 is a pinning test only.
- **Evidence** (probe, 2026-09-28): `encode_save` → `decode_save` returned equal values *of the same
  type and `repr`* for `-5`, `-1.5`, `1.0`, `-0.0`, `1e16`, `5e-324`, `0.30000000000000004`, `""`,
  `2**63 - 1` and `-(2**63)`. Python's `json` writes floats with a round-tripping `repr`, keeps
  `1.0` as a float on load, and writes `""` as `""`.
- **Test**: US4-AS5 plays a story whose givens set a negative int, a float and `""`, saves, resumes,
  and compares `type(v)` and `v` for each; a hypothesis property over the storable domain
  (`integers(-(2**63), 2**63-1) | floats(allow_nan=False, allow_infinity=False) | text()` minus
  surrogates) guards the codec directly.

### PD-15. Acceptance tests stay plain pytest

- **Decision**: Follow 001's PD-15. Plain pytest end-to-end tests marked `acceptance`, docstrings
  naming spec scenarios (`US1-AS3`). No Gherkin, no `specs/acceptance-specs/`, no pytest-bdd.
  Files go in a new subpackage, `tests/acceptance/spec_compliance/`, so their `test_usNN_*` names
  don't collide with 001's `tests/acceptance/test_us01_*.py` … `test_us06_*.py`.
- **Rationale**: The pipeline in the plan template doesn't exist in ravel (see the acceptance-tests
  skill's status note); 001 already chose not to add it.

### PD-16. Spec examples run as tests (FR-020, US6)

- **Decision**: `tests/test_spec_examples.py` *reads* `docs/RAVEL_LANGUAGE_SPEC.md` at test time,
  extracts examples from fenced code blocks under §4, §5, §6, §7, §9 and §11.4, and runs each as a
  parametrized case whose id is `§<section>: <example text>`. Full format in
  [contracts/spec-examples.md](contracts/spec-examples.md). In short:
  - **Result lines** (`… → result`) carry their own expected value: an expression, or a `;`-chained
    setup of operations ending in an operation or comparison. §5.1 already uses this form; v0.2
    adds result lines for precedence, negatives, `""`, references, `value` and constraints.
  - **YAML examples** (items under `given:`/`effect:`, items under `when:`, and `{…}` prefixes)
    must compile as an operation or comparison and evaluate against empty qualities without
    raising.
  - A guard test pins the extracted count per section, so an extractor that silently finds nothing
    fails, and so does adding or deleting an example without updating the pin.
- **Why read the doc instead of copying examples into the test**: US6-AS2 requires that editing an
  expected result *in the spec* fails a test that names the example. A hand-copied table can't see
  the edit.
- **Alternatives**: doctest over the markdown (the examples aren't Python); a new
  `ravel-example` fence language (renames many existing blocks, against "rewrite as little as
  possible").

### PD-17. Grammar tasks keep backslashes doubled (deferred item 2)

- **Decision**: Every task that edits `grammars.py` carries the acceptance criterion: *every regex
  backslash in the new grammar text is doubled (`\\s`, `\\d`, `\\b`, `\\W`, `\\w`, `\\[`), and
  `uv run pytest tests/test_grammars.py` passes*. `plain_text_grammar`'s `"\n"` stays single.
- **Also**: `ComparisonParser.grammar` is built inline in `parsers.py` from
  `"comparison = …" + grammars.base_expression_grammar`, duplicating `grammars.comparison_grammar`.
  It switches to `Grammar(grammars.comparison_grammar)` so the guard test covers the grammar the
  parser actually uses.

### PD-18. VM spec v0.2 structure (FR-018)

- **Decision**: Rewrite `docs/RAVEL_VM_SPEC.md` around the shipped engine, reusing its still-valid
  vocabulary. Sections: 0 Status and scope · 1 Introduction (goals: deterministic, savable, I/O-free,
  embeddable) · 2 Domain model (`Story`, `GameState`, `Qualities`, `Frame`, `Status`, `Outcome`,
  compiled directive types) · 3 Engine API (`start`/`choose`/`present`/`resume`, errors) · 4 Outputs
  (the seven types) · 5 Execution semantics (run loop, choice blocks, query mode and its sort,
  `end`) · 6 Expressions, operations and constraints at run time · 7 Determinism guarantee · 8 Save
  format v1 (points at `ravel.app.saves` and restates the contract) · 9 Ports and adapters
  (`StorySource`, `SaveStore`, `Loader`, filesystem and memory adapters, `GameSession`) · 10 Host
  recipes (realtime, async, HATEOAS; recipes only, nothing ships) · 11 Glossary · Appendix A
  Design history (a short summary of the 0.1 instruction-set design, layered qualities, event bus and
  JSON IR, each marked *deferred* or *not planned*). The 0.1 `AT-*` tests are dropped; the real
  acceptance tests are named instead.
- **Fix in passing**: §0's table marks Expression and Constraint "Implemented"; 0.1 was wrong. The
  v0.2 status table only lists what this feature ships.
- **Rationale**: David, 2026-09-28: "the VM spec should be rewritten to match the engine." The
  contracts in `specs/001-reentrant-vm/contracts/` are the detailed source; the VM spec summarizes
  and links rather than duplicating byte-level detail.

---

## Prior decisions this plan relies on

- 001 PD-03: the engine interprets compiled directives; no IR. VM spec v0.2 keeps that.
- 001 PD-15/PD-16: plain-pytest acceptance tests and the hypothesis settings reused in PD-13/PD-15.
- 001 2026-09-28 save revision (story-free `decode_save`, anchors): unchanged; PD-13 builds on it.
- Spec-doc history (`git log -- docs/RAVEL_LANGUAGE_SPEC.md docs/RAVEL_VM_SPEC.md`): `52a9c7b` (VM
  spec status annotations), `300a2df` (`end` directive, §9.4/§10.2/§11.2), `12180c4` (syml 1.0
  re-indent). None of them settled any question this feature reopens.

## NEEDS CLARIFICATION

None. Every deferred item in the spec is resolved above (PD-12, PD-17, PD-14, PD-05, PD-07/PD-08).
