# Solution Index

Solutions are organized by category. Each entry links to a detailed solution document.

## Categories

| Category              | Description                                              |
| ---------------------- | --------------------------------------------------------- |
| `python-typing/`       | mypy config quirks (`files = ["src", "tools"]`, not strict), typing gaps |
| `ruff/`                | Lint rule conflicts, formatting conflicts (ravel's smaller `select` set) |
| `pytest-coverage/`     | 100% branch coverage patterns, fixtures                   |
| `parsing/`             | Parsimonious grammar quirks, PEG lexing/compiler edge cases |
| `spec-conformance/`    | Spec-vs-implementation gaps (`docs/RAVEL_LANGUAGE_SPEC.md`, `docs/RAVEL_VM_SPEC.md`) |
| `security/`            | Input validation, resource limits, unsafe-input handling  |
| `clean-architecture/`  | Layer boundaries, compiler/VM dependency direction        |
| `tooling/`             | pre-commit hooks, `uv`/`br` dependency issues              |

## Solutions

_(none yet — entries are added here as they are discovered, one file per
category directory, e.g. `tooling/<slug>.md`, linked from this index.)_

## How to Update This File

When a session resolves a non-obvious gotcha, add an entry under the matching
category using this format:

    ### category

    - [Short Problem Title](category/slug.md) — one-line summary of the fix (YYYY-MM-DD)
