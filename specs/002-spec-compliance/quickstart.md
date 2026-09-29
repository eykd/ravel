# Quickstart: Ravel Spec Compliance (002)

How to see each user story working once the feature lands. All commands run from the repo root.

## Full gate

```sh
./runtests.sh                          # 100% branch coverage, all tests
uv run pytest -m acceptance tests/acceptance/spec_compliance
uv run pytest tests/test_spec_examples.py tests/test_grammars.py
uv run ruff check && uv run ruff format --check && uv run mypy
uv run pre-commit run --all-files
```

## US1 and US2: expressions and constraints

```python
from ravel import parsers


def run(src, **qualities):
    op = parsers.OperationParser().parse(src)
    return op.evaluate(qualities.get(op.quality), qualities=qualities)


run("X = 10 - 4 - 2")  # 4
run("X = 2 + 3 * 4")  # 14
run("X = 10 - -4")  # 14
run('X = ""')  # ''
run("X = [Health] + Bonus", Health=7, Bonus=3)  # 10
run("X += value * 2", X=10)  # 30
run("X -= 10 min 0", X=5)  # 0
run("X += 10 max 8", X=5)  # 8
```

## US3: concept lines, include cycles, `text:` in choices

```python
from ravel.environments import Environment
from ravel.loaders import MemoryLoader

env = Environment(
    loader=MemoryLoader(
        {
            "begin": "include:\n  - other\n\ndeclared:\n  - Situation\n  - Here[.] you are.\n",
            "other": "include:\n  - begin\n\nthere:\n  - There[.] it is.\n",
        }
    )
)
book = env.load()  # the begin <-> other cycle loads, each file once
book["rulebook"]["Situation"]["locations"]["begin::declared"].intro  # Text(text='Here.')
```

## US4: embed the engine with no filesystem

```python
from ravel import engine
from ravel.adapters.story_source import MemoryStorySource
from ravel.app.saves import decode_save, encode_save

SOURCE = (
    "given:\n  - Location = 'Start'\n  - Gold = 1\n\n"
    "start:\n  - when:\n      - Location = 'Start'\n  - Ready.\n"
    "  - choice:\n      - [Go]Going.\n      - effect:\n          - Gold = 2\n          - Location = 'Done'\n\n"
    "done:\n  - when:\n      - Location = 'Done'\n  - Finished.\n"
)

story = MemoryStorySource({"begin": SOURCE}).load()
step = engine.start(story)  # step.state.offered == ('begin::start',)
save = encode_save(story, step.state)

# One stateless request: bytes in, bytes out, no session held between requests.
step = engine.resume(story, decode_save(save))
step = engine.choose(story, step.state, step.state.offered[0])
save = encode_save(story, step.state)  # bytes; step.state.offered == ('begin::start::go',)
```

`Environment()` with no loader now raises `TypeError`; pass `FileSystemLoader(base_path=...)` or
`MemoryLoader({...})`.

## US5: docs

- `docs/RAVEL_LANGUAGE_SPEC.md` is v0.2: rulings R1–R8, a precedence table in §5.1, §10.1 matching
  `grammars.py`, §12 matching `examples/cloak`.
- `docs/RAVEL_VM_SPEC.md` is v0.2: the shipped engine, ports, host recipes; the 0.1 design is a
  short Appendix A.

## US6: spec examples are tests

```sh
uv run pytest tests/test_spec_examples.py -v   # one case per spec example, id names it
```

Change `10 - 4 - 2        → 4` in §5.1 to `→ 8` and rerun: the case
`§5.1:<line>: 10 - 4 - 2 → 8` (e.g. `§5.1:248: 10 - 4 - 2 → 8`) fails.

## Cloak regression (SC-005)

```sh
uv run ravel run examples/cloak     # play to the win ending, then again to the loss ending
```
