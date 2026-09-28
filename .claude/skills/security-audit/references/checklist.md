# Security Review Checklist

Quick reference for security audits of a QBN compiler/VM library. Check each
item and flag issues by severity.

## Untrusted Input Handling

- [ ] Input size is bounded before loading/compiling begins (no unbounded `read()`)
- [ ] Loader rejects or streams inputs above a documented size limit
- [ ] Encoding is validated/normalized before lexing (no silent mojibake)
- [ ] Malformed input raises a typed error (`ravel.exceptions.ParseError` /
      `OutOfContextNodeError`), never an unhandled exception from deep in the
      grammar or compiler

## Resource Exhaustion (Recursion & Stack Depth)

See [rate-limiting.md](rate-limiting.md) for the full DoS-prevention writeup.

- [ ] Recursive descent (or PEG rule recursion) has an explicit depth limit
- [ ] Deeply nested input (thousands of nested predicate/effect levels) fails
      gracefully with a `ParseError`, not a `RecursionError`/segfault
- [ ] The compiler's directive/effect walkers bound how deep they recurse per rule
- [ ] `Environment.load_rulebook`'s BFS over `include:` names has some bound
      on the number of distinct rulebooks it will chase
- [ ] No unbounded recursion driven directly by attacker-controlled nesting depth

## Regular Expression Denial of Service (ReDoS)

- [ ] No user-influenced regex with nested quantifiers (`(a+)+`, `(a*)*`) or
      overlapping alternation that can catastrophically backtrack
- [ ] Parsimonious grammar rules in `grammars.py` that use regex terminals are
      checked for backtracking blowup on adversarial input (long runs of
      near-matches)
- [ ] Regex-based text lexing has been fuzzed or stress-tested with
      pathological strings (long lines, long runs of glue/predicate markers, etc.)

## File Handling

See [metadata-validation.md](metadata-validation.md) for implementation detail.

- [ ] `FileSystemLoader.get_source` never resolves a rulebook `name` that
      escapes `base_path` (validate/allowlist `name` before it reaches
      `Environment.load()`/`load_rulebook()`)
- [ ] Error messages that embed a rulebook name or path don't let
      attacker-controlled strings inject terminal escape sequences or
      absolute-path disclosure beyond what the caller already provided
- [ ] Large files are not read fully into memory without a documented limit
- [ ] No implicit following of symlinks or expansion of paths inside parsed
      content (rulebook values are plain strings — never treated as paths)

## Parser/Compiler Correctness as a Security Boundary

- [ ] Grammar changes are checked against `docs/RAVEL_LANGUAGE_SPEC.md` and
      `docs/RAVEL_VM_SPEC.md` and their recorded decisions before "fixing"
      behavior — silent behavior drift is itself a risk for downstream
      consumers who load untrusted stories
- [ ] The compiler never partially returns a mix of compiled and uncompiled
      fragments on error (fail closed, not partially open)
- [ ] `Source`/`Pos` objects don't leak more of the host filesystem than the
      caller already provided

## Error Handling

- [ ] Errors carry position info (`Pos`) but not internal compiler/VM state
      or stack traces beyond what's useful for the caller
- [ ] `ParseError`/`OutOfContextNodeError` messages don't reflect back raw
      attacker input in a way that could be used for log injection
- [ ] Fail secure: on ambiguous or malformed input, raise rather than guess

## Secrets Management

- [ ] No hardcoded secrets or tokens in source, tests, or fixtures
- [ ] CI secrets (PyPI publish tokens, etc.) live in GitHub Actions secrets,
      never in `pyproject.toml` or committed files
- [ ] Secrets are not logged or included in exception messages

## Dependency & Supply Chain

- [ ] `uv.lock` is committed and kept in sync (`uv-lock` pre-commit hook)
- [ ] Runtime dependencies (Parsimonious) are pinned to a reviewed range
- [ ] No dependency is a known typosquat or has a recent CVE unaddressed

## Audit & Monitoring

- [ ] Fuzz/property tests exist for loader/compiler entry points (`Environment.load()`, `compile_rulebook`)
- [ ] Regression tests exist for any parser bug that was previously a DoS
      or crash vector

---

## Severity Guide

### Critical (Fix Immediately)

- Unbounded recursion reachable from untrusted input (stack exhaustion / crash)
- ReDoS-vulnerable regex reachable from untrusted input
- Hardcoded secrets
- Unhandled exception (not `ParseError`) escaping from malformed input

### High (Fix Before Release)

- Missing input size limits allowing memory-exhaustion DoS
- Error messages leaking more filesystem/environment detail than intended
- Silent data corruption on malformed input (partial `as_data()` results)

### Medium (Fix Soon)

- Missing fuzz/property coverage for a known-tricky grammar rule
- Verbose error messages beyond what callers need
- Unpinned or loosely pinned dependency ranges

### Low (Track for Fix)

- Missing regression test for a fixed crash
- Minor inconsistency between spec and implementation noted in the feature's `research.md`
