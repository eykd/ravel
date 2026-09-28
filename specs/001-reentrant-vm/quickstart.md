# Quickstart: 001-reentrant-vm

## Play, save, load, win (terminal)

```sh
uv sync
uv run ravel run examples/cloak
#   pick by number; `save` writes ./ravel-save.json; `q` quits
uv run ravel run examples/cloak --load ravel-save.json
#   resumes at the saved menu; givens are not re-applied
```

Win route (by label): intro → Press onward! → cloakroom → look → look → the hook → hang up
cloak → leave → bar → look → look → read the message. The game prints `**You have won**` and
`*** The End (outcome: won) ***`, then exits 0.

Prompt commands: a number, `save [FILE]`, `load [FILE]`, `s` (qualities), `help`/`?`, `q`.

## Drive the engine from Python

```python
from ravel.adapters.story_source import FileSystemStorySource
from ravel import engine

story = FileSystemStorySource("examples/cloak").load()
step = engine.start(story)  # Step(state, outputs)
step = engine.choose(story, step.state, "begin::intro")
for out in step.outputs:
    print(out)  # TextShown(...), ChoicesOffered(...), ...
```

## With save/load (application layer)

```python
from ravel.app.session import GameSession
from ravel.adapters.save_store import FileSaveStore

session = GameSession(story, FileSaveStore())
session.new_game()
session.choose("begin::intro")
session.save("mid.json")

fresh = GameSession(story, FileSaveStore())
fresh.load("mid.json")  # -> (ChoicesOffered(...),)
```

## Verify

```sh
./runtests.sh                                    # 100% branch coverage gate
uv run pytest -m acceptance                      # user-story end-to-end tests
uv run pytest tests/acceptance/test_us06_save_load_property.py   # 200 hypothesis cases
uv run mypy && uv run pre-commit run --all-files
```

## Author an ending

```yaml
look-at-message:
  - when:
      - Bar >= 2
  - **You have won**
  - end: won
```

Note the syml 1.0 rule: a list under `- when:` / `- choice:` / `- effect:` must be indented past
the key's column (two more spaces than the `-`).
