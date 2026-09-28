# Contract: Session API and Ports (`ravel.app`) — application layer

## Ports (`ravel.app.ports`)

```python
class StorySource(Protocol):
    def load(self) -> Story: ...  # compile once; raises ravel.exceptions.* on bad source


class SaveStore(Protocol):
    def write(self, name: str, data: bytes) -> str: ...  # returns a display path; OSError propagates
    def read(self, name: str) -> bytes: ...  # FileNotFoundError → mapped by session
```

Adapters (`ravel.adapters`):

```python
class FileSystemStorySource:  # story_source.py
    def __init__(self, directory: str | os.PathLike[str]) -> None: ...
    def load(self) -> Story: ...  # Environment(loader=FileSystemLoader(directory)).load() → Story.from_rulebook


class FileSaveStore:  # save_store.py
    def __init__(self, base: Path | None = None) -> None: ...  # None → Path.cwd() at call time
    def write(self, name: str, data: bytes) -> str: ...  # temp file in same dir + os.replace (atomic, overwrites)
    def read(self, name: str) -> bytes: ...
```

## `GameSession` (`ravel.app.session`)

```python
DEFAULT_SAVE_NAME: Final = "ravel-save.json"


class GameSession:
    def __init__(self, story: Story, saves: SaveStore) -> None: ...
    @property
    def story(self) -> Story: ...
    @property
    def state(self) -> GameState: ...  # NoGameError if none started/loaded
    def menu(self) -> tuple[ChoiceOption, ...]: ...  # () unless waiting
    def new_game(self) -> tuple[Output, ...]: ...  # engine.start; replaces state
    def choose(self, location: LocationId) -> tuple[Output, ...]: ...  # engine.choose; EngineError → state kept
    def save(self, name: str = DEFAULT_SAVE_NAME) -> str: ...  # returns display path
    def load(self, name: str = DEFAULT_SAVE_NAME) -> tuple[Output, ...]: ...  # returns engine.present(...)
```

Rules:
- The session is the only mutable holder; it assigns `self._state` only after the engine or the
  decoder returned successfully (FR-015, FR-024: a refused load leaves the live game untouched).
- `save` requires a state (`NoGameError` otherwise) and writes `encode_save(story, state)`.
- `load` = `saves.read` → `decode_save(story, data)` → assign → `engine.present`. It never calls
  `engine.start`, so givens are never re-applied (FR-023).
- A session built for a CLI run compiles the story once; later `load`s check against that
  compilation even if files changed on disk (edge case "story edited during session").

## Errors (`ravel.app.saves`, re-exported from `ravel.app`)

```python
class SessionError(Exception): ...


class NoGameError(SessionError): ...


class LoadRefusedError(SessionError): ...  # base: every refused load


class SaveNotFoundError(LoadRefusedError): ...  # "no save file at 'x'"


class SaveCorruptError(LoadRefusedError): ...  # "not valid JSON: …" / "missing field 'state.stack'" / "…must be an int"


class UnsupportedSaveVersionError(LoadRefusedError): ...  # "unsupported save format version 2 (this ravel reads 1)"


class StoryChangedError(LoadRefusedError): ...  # "the story has changed since this save was made"


class UnknownLocationError(LoadRefusedError): ...  # "save refers to location 'x', which the story does not have"
```

`InvalidStateError` from `engine.validate_resumable` is re-raised as `SaveCorruptError` (chained).

## Example (US4-AS2/AS3)

```python
story = FileSystemStorySource("examples/cloak").load()
a = GameSession(story, FileSaveStore(tmp_path))
a.new_game()
a.choose("begin::intro")
a.save("mid.json")

b = GameSession(story, FileSaveStore(tmp_path))
outs = b.load("mid.json")
outs == (ChoicesOffered((ChoiceOption("begin::intro::press-onward", "Press onward!"),)),)
b.state == a.state
assert b.choose("begin::intro::press-onward") == a.choose("begin::intro::press-onward")
```
