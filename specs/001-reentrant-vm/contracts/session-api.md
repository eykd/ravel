# Contract: Session API and Ports (`ravel.app`) — application layer

## Ports (`ravel.app.ports`)

```python
class StorySource(Protocol):
    def load(self) -> Story: ...  # compile once; raises ravel.exceptions.* on bad source


class SaveStore(Protocol):
    def write(self, name: str, data: bytes) -> str: ...  # returns a display path; OSError propagates
    def read(self, name: str) -> bytes: ...  # at most MAX_SAVE_BYTES + 1 bytes; OSError → mapped by session
```

Adapters (`ravel.adapters`):

```python
class FileSystemStorySource:  # story_source.py
    def __init__(self, directory: str | os.PathLike[str]) -> None: ...
    def load(self) -> Story: ...  # Environment(loader=FileSystemLoader(directory)).load() → Story.from_rulebook


class FileSaveStore:  # save_store.py
    def __init__(self, base: Path | None = None) -> None: ...  # None → Path.cwd() at call time
    # write: temp file (mkstemp in the target dir) + os.replace; temp removed on failure;
    # mode 0o666 & ~umask. Clobber guard: an existing non-empty file that does not start
    # with SAVE_MAGIC → FileExistsError.
    def write(self, name: str, data: bytes) -> str: ...

    # read: refuses non-regular files (os.stat + S_ISREG before open: FIFOs/devices/dirs →
    # OSError); reads at most MAX_SAVE_BYTES + 1 bytes (decode_save rejects the oversize).
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
  decoder returned successfully (FR-015, FR-024: a *refused* load leaves the live game untouched;
  a load that merely truncates against a changed story still only assigns after `resume`
  succeeds, which it always does).
- `save` requires a state (`NoGameError` otherwise) and writes `encode_save(story, state)`.
- **2026-09-28 revision**: `load` = `saves.read` → `decode_save(data)` (story-free) →
  `engine.resume(story, saved)` → assign → return `resume`'s outputs verbatim. It never calls
  `engine.start`, so givens are never re-applied (FR-023). It never calls `engine.present`
  separately — `resume` already re-derives and returns the pending menu (or halt).
- `load` raises **only** `LoadRefusedError` subclasses: `FileNotFoundError` → `SaveNotFoundError`;
  any other `OSError` from `read` (permission, directory, not a regular file) →
  `SaveUnreadableError`; everything `decode_save` raises is already a `LoadRefusedError`.
  **`engine.resume` never raises** — a changed story degrades the load (truncation +
  `StoryChanged`) instead of refusing it, so there is no `StoryChangedError` and no
  `UnknownLocationError` any more.
- `choose` propagating an author error (`TypeError`, `ZeroDivisionError`,
  `InvalidQualityValueError`) keeps the previous state.
- A session built for a CLI run compiles the story once; later `load`s resolve against that
  compilation even if files changed on disk (edge case "story edited during session") — a save
  from *before* the edit truncates exactly as if loaded fresh against the edited directory.

## Errors (`ravel.app.saves`, re-exported from `ravel.app`)

```python
class SessionError(Exception): ...


class NoGameError(SessionError): ...


class LoadRefusedError(SessionError): ...  # base: every refused load


class SaveNotFoundError(LoadRefusedError): ...  # "no save file at 'x'"


class SaveUnreadableError(LoadRefusedError): ...  # "cannot read save file 'x': <strerror>"


class SaveCorruptError(LoadRefusedError): ...  # "not valid JSON: …" / "missing field 'state.stack'" / "…must be an int"


class UnsupportedSaveVersionError(LoadRefusedError): ...  # "unsupported save format version 2 (this ravel reads 1)"


# Every message quotes save-sourced strings with repr() (%r), so control characters are escaped.
```

**2026-09-28 revision**: `StoryChangedError` and `UnknownLocationError` are **removed**. Both
were refusals for exactly the two conditions ("story changed", "unknown location") that are now
handled by truncation inside `engine.resume` instead — see engine-api.md § `resume`. There is no
more `InvalidStateError`-from-`validate_resumable` path either: `validate_resumable` is removed
(engine-api.md).

## Example (US4-AS2/AS3, unchanged story)

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

## Example (US4-AS4, story changed since save — 2026-09-28)

```python
# `a` saved mid-game against `story`. `story` is then edited so that the situation `a` was
# waiting in no longer exists (its `location` was deleted).
edited_story = FileSystemStorySource(edited_dir).load()
c = GameSession(edited_story, FileSaveStore(tmp_path))
outs = c.load("mid.json")  # never raises

assert outs[0] == StoryChanged(dropped=("begin::intro::press-onward",))
assert isinstance(outs[1], ChoicesOffered)  # the top-level query menu, re-derived fresh
assert c.state.stack == ()  # every frame above the deleted one is gone too
```

If instead only an unrelated situation elsewhere in the story changed, `c.load("mid.json")`
returns exactly `a`'s original `(ChoicesOffered(...),)` with **no** `StoryChanged` — the anchor
still matches.
