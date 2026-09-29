# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ravel is a Python engine and authoring language for Quality-Based Narratives (QBN) — the
storylet model from Failbetter Games, with syntax borrowed from Ink and YAML. Author `.ravel`
files; the compiler turns them into a rulebook; the pure `ravel.engine` interprets it.

## Environment & commands

The project targets Python 3.14 and is driven by `uv`. `.python-version` pins the interpreter;
`uv sync` fetches it and builds `.venv/` from `uv.lock`. `.venv/` is not committed.

```sh
uv sync
uv run pytest
```

- Full suite with coverage: `./runtests.sh` (adds `--failed-first --exitfirst --cov=ravel
  --cov-branch --no-cov-on-fail`; forwards extra args). Coverage is at 100% and
  `fail_under = 100` in `pyproject.toml` holds it there — new code needs tests, and there are
  no `# pragma: no cover` marks left in `src/` to imitate.
- One file / one test: `uv run pytest tests/test_parsers.py` ·
  `uv run pytest tests/test_parsers.py::test_name`
- Watch mode: `uv run --with pytest-watcher ptw .`
- Lint + format: `uv run pre-commit run --all-files` — ruff (check + format) replaces the old
  isort/flake8/black trio. Line length 120. `UP031` (printf-style `%` formatting) is ignored
  deliberately; the codebase uses it throughout for error messages.
- Type check: `uv run mypy` (config in `pyproject.toml`). Clean, and enforced as a `local`
  pre-commit hook — not `mirrors-mypy`, which runs in an isolated venv where `attr` and `click`
  become missing-stub errors. Typing is partial: a `[[tool.mypy.overrides]]` block makes
  `ravel.engine.*`, `ravel.app.*`, `ravel.adapters.*`, `ravel.cli`, `ravel.types` and
  `ravel.queries` strict (`check_untyped_defs`, `disallow_untyped_defs`, `disallow_incomplete_defs`,
  `disallow_any_generics`, `warn_return_any`, `strict_equality`; deliberately not
  `disallow_untyped_calls`, since adapters call unannotated `Environment`/compiler functions).
  Everywhere else most function bodies are unannotated, so mypy skips them.
- Run a story: `uv run ravel run examples/cloak` (console script `ravel = ravel.cli:main`;
  `--verbose`/`--debug` are group-level flags, before the subcommand).
- CI: `.github/workflows/main.yml` runs pytest with branch coverage, `ruff check`,
  `ruff format --check`, and `mypy` on every push and pull request. Single job — no matrix,
  since `requires-python = ">=3.14"`.

`src/ravel/grammars.py` holds the PEG text in raw strings, so every regex backslash must be
doubled (`~'[^\\s]+'`): parsimonious `literal_eval`s the token text, and a single backslash
raises `SyntaxWarning` today and `SyntaxError` on a future Python. `tests/test_grammars.py`
rebuilds all five grammars under an error filter to catch a regression. The exception is
`plain_text_grammar`'s `"\n"`, which is a valid escape and must stay single.

Rulebooks load through `syml.parsers.parse(...).as_source()`, not `syml.loads`, so nodes keep
their `Source` (filename, line, column) and parse errors can name where the bad text came from.
Predicate targets must reach `compile_predicate` unflattened for that to survive — use
`get_list_of_sources`, not `get_list_of_texts`.

## Architecture

The pipeline is: `.ravel` source → `Environment` → `Loader` → compiler → rulebook dict →
`ravel.engine` (`start`/`choose`/`present`/`resume`) → `ravel.app.GameSession` → an adapter
(`ravel.cli.ConsoleUI`, or any other caller of `GameSession`).

**Loading and merging** (`environments.py`, `loaders.py`). `Environment.load()` starts at the
`begin` rulebook and walks `include:` breadth-first, caching each compiled rulebook and
invalidating it on file mtime. Rule names are namespaced as `filename::rulename` via
`location_separator`. All loaded rulebooks merge into one master dict keyed by concept, each
holding `{"rules": [...], "locations": {...}}`, plus flattened `metadata` and `givens`.

**Compiling** (`compiler/`). `compile_preamble` consumes top-level `include` / `given` / `when` /
`about` keys until it hits the first real rule, then hands the rest off. A top-level `when:`
becomes *common predicates* prepended to every rule in that file. Each rule compiles into a
`types.Rule(name, predicates)`; its body ("baggage") is dispatched through a concept-handler
registry — `@concepts.handler("Situation")` in `situations.py`, registered by import side effect
from `compiler/__init__.py`. Unregistered concepts fall through to `_dummy_handler`, which is how
custom concepts stay cheap. Directives compile to the small attrs value types in `types.py`
(`Text`, `Choice`, `Operation`, `Comparison`, `BeginChoices`, `GetChoice`).

**Querying** (`queries.py`). This is the QBN core. `query()` tests the current qualities against
every rule's predicates and scores each match by `len(rule.predicates)`, so the most specific
matching rule wins. `query_by_name` resolves a rule name back to its compiled baggage via the
concept's `locations` map.

**The engine** (`ravel/engine/`). Pure and re-entrant: no mutable module state, no signals, no
callbacks. `GameState` is immutable (`Frame(location, ip)` tuples on `state.stack`, plus
`qualities`/`status`/`outcome`); every call takes a `Story` and a `GameState` and returns a `Step`
(new `GameState` + a tuple of `Output`s) — `start(story)`, `choose(story, state, location)`,
`present(story, state)`, `resume(story, saved)`. `ip` indexes a situation's compiled directives;
running a frame dispatches on directive type (`Text`, `Operation`, `BeginChoices`, `End`) until it
yields at a choice block or the stack empties into query mode. `ravel.engine.outputs` defines the
seven frozen output types engines can emit (`TextShown`, `ChoicesOffered`, `QualityChanged`,
`SituationEntered`, `SituationExited`, `Halted`, `StoryChanged`) — plain values, never sent over a
signal. `ravel.app.GameSession` (`ravel/app/session.py`) is the one mutable holder: it owns a
`Story` and a `SaveStore` and turns engine calls into `new_game`/`choose`/`save`/`load`. Adapters
(`ravel.cli.ConsoleUI`) render a session's outputs and drive its prompt loop; nothing calls the
engine directly except `GameSession`.

**Grammars** (`grammars.py`, `parsers.py`). Parsimonious PEGs, composed by string concatenation
from a shared `base_expression_grammar`. They cover expressions, comparisons, operations with
`max`/`min` constraints, `[bracketed]` intro text, `<>` glue, and `{quality == value}` line
prefixes. Change the grammar and the parser node visitor in `parsers.py` together.

## Language reference

`docs/RAVEL_LANGUAGE_SPEC.md` documents the authoring language and is kept in sync with what the
compiler accepts. `docs/RAVEL_VM_SPEC.md` predates the pure `ravel.engine` rewrite and describes a
different, instruction-set VM design; it now carries implemented/deferred annotations pointing at
the real engine and `specs/001-reentrant-vm/contracts/` — read the annotations, not the
instruction-set body, for current behavior. Both files are tracked by git. `examples/cloak/` is
the fullest worked example; `tests/conftest.py` loads it as a fixture.
