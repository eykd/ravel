# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ravel is a Python engine and authoring language for Quality-Based Narratives (QBN) — the
storylet model from Failbetter Games, with syntax borrowed from Ink and YAML. Author `.ravel`
files; the compiler turns them into a rulebook; a stack VM performs them.

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
  pre-commit hook — not `mirrors-mypy`, which runs in an isolated venv where `attr`, `click`,
  and `blinker` all become missing-stub errors. Typing is still partial: most function
  bodies are unannotated, so mypy skips them unless `check_untyped_defs` is turned on.
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

`src/ravel/vm/events.py` imports `State` and `Choice` under `if TYPE_CHECKING:` and then uses
them as annotations in attrs `field()` declarations. That only works because PEP 649 defers
annotation evaluation on 3.14 — on 3.10 the module raised `NameError` at import and two test
files failed at collection. Do not "fix" it by dropping the `TYPE_CHECKING` guard without
understanding this; equally, do not assume the pattern is safe to spread to code that must run
on older interpreters.

## Architecture

The pipeline is: `.ravel` source → `Environment` → `Loader` → compiler → rulebook dict → `VirtualMachine` → `Runner`.

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

**The VM** (`vm/`). `VirtualMachine` is a stack of `State` objects plus a FIFO action queue.
`push`/`pop` *enqueue* work; `do_push`/`do_pop` execute it — mixing the two is how ordering bugs
appear. States are `Begin` → `DisplayPossibleSituations` → `DisplaySituation`;
`DisplaySituation.display` walks directives and dispatches on `handle_<lowercased classname>`,
stopping when it hits a `GetChoice` or the end. Everything the outside world sees is a frozen
attrs event from `vm/events.py` sent over blinker signals (`vm/signals.py`); a `Runner`
(`vm/runners.py`, and `ConsoleRunner` in `cli.py`) subscribes to those signals. Input comes back
in through the `send_input` callable on a `waiting_for_input` event, never by calling the VM.

**Grammars** (`grammars.py`, `parsers.py`). Parsimonious PEGs, composed by string concatenation
from a shared `base_expression_grammar`. They cover expressions, comparisons, operations with
`max`/`min` constraints, `[bracketed]` intro text, `<>` glue, and `{quality == value}` line
prefixes. Change the grammar and the parser node visitor in `parsers.py` together.

## Language reference

`docs/RAVEL_LANGUAGE_SPEC.md` and `docs/RAVEL_VM_SPEC.md` are detailed working specs derived from
the implementation — read them rather than re-deriving semantics. Both are currently untracked by
git. `examples/cloak/` is the fullest worked example; `tests/conftest.py` loads it as a fixture.
