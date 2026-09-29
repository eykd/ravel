# Contract: Embedding — in-memory sources, required loader, stateless cycle, determinism, saves (FR-012 – FR-016)

**Surface**: `ravel.environments.Environment` (**breaking**: `loader` required),
`ravel.loaders.MemoryLoader` (new), `ravel.adapters.story_source.MemoryStorySource` (new),
existing `ravel.engine` / `ravel.app.saves` (unchanged, newly pinned).

## `Environment` (FR-013, PD-12) — Principle VI break

```python
@attr.s
class Environment:
    loader: Loader = attr.ib(validator=_has_load)  # no default
    location_separator: str = attr.ib(default="::")
    initializing_name: str = attr.ib(default="begin")
    cache: dict[str, Any] = attr.ib(factory=dict)
```

- `Environment()` → `TypeError` (attrs' "missing 1 required positional argument: 'loader'").
- `Environment(loader=object())` → `TypeError("Environment loader must have a callable load(); got object")`.
- `environments.py` no longer imports `ravel.loaders`.

## `MemoryLoader` (FR-012, PD-11)

```python
class MemoryLoader(BaseLoader):
    def __init__(self, sources: Mapping[str, str]) -> None: ...  # copies into a dict
    def get_source(self, environment: Environment, name: str) -> tuple[str, Callable[[], bool]]:
        """Return (source, always-up-to-date); RulebookNotFound(name) if absent."""
```

```python
env = Environment(loader=MemoryLoader({"begin": "intro:\n  - Hi[.] there.\n"}))
env.load()["rulebook"]["Situation"]["rules"]  # [Rule("begin::intro", [])]
Environment(loader=MemoryLoader({})).load()  # raises RulebookNotFound("begin")
```

## `MemoryStorySource` (FR-012, PD-11)

```python
class MemoryStorySource:
    def __init__(self, sources: Mapping[str, str], *, entry: str = "begin") -> None: ...
    def load(self) -> Story: ...  # satisfies ravel.app.ports.StorySource
```

```python
session = GameSession(MemoryStorySource({"begin": SRC}).load(), saves=InMemorySaveStore())
session.new_game()  # plays with zero filesystem reads (SC-003)
```

(`InMemorySaveStore` is the test double from 001's property test; no new save adapter ships.)

**How "zero filesystem reads" is tested (US4-AS1).** After all imports, one
`pytest.MonkeyPatch.context()` replaces `builtins.open`, `io.open`, `os.open` and `os.stat` with
functions raising `AssertionError`, around `load()`, `new_game()` and one `choose` only. In the same
context, `FileSystemStorySource(tmp_path).load()` over a pre-written one-file story must raise that
`AssertionError` (positive control), so the check can't pass vacuously. See plan.md, "Proving zero
filesystem reads".

## Stateless request/response (FR-014, PD-13)

No new API. The recipe the acceptance test and VM spec §10 use:

```python
def handle(story: Story, save: bytes, location: LocationId) -> tuple[bytes, tuple[Output, ...]]:
    step = engine.resume(story, decode_save(save))
    step = engine.choose(story, step.state, location)
    return encode_save(story, step.state), step.outputs
```

Guarantee: for any waiting state `s` reached this way, `engine.resume(story,
decode_save(encode_save(story, s))).state == s`, and re-encoding gives the same bytes.

**Trust boundary (RT-4).** `decode_save` checks shape and `MAX_SAVE_BYTES` only; save bytes are not
tamper-evident, and a client holding them can forge any quality or stack. `choose` still refuses a
location outside `state.offered` (`NotOfferedError`). A host that sends save bytes to the client
must keep saves server-side behind an opaque id, or authenticate the bytes (e.g. HMAC with a
server-held key) before `decode_save`. The engine ships neither; VM spec §10 states this in the
HATEOAS recipe.

## Determinism (FR-015, PD-13)

Guarantee: for a `Story` compiled from the same sources and the same sequence of `choose`
locations, `start`/`choose` return equal `Step`s (equal output tuples, equal `GameState`s) and
`encode_save` returns equal bytes, across repeated runs and across freshly compiled `Story`
objects. The engine has no randomness, clock or I/O; this contract pins that.

## Save values (FR-016, PD-14)

Save format stays **v1**. Guarantee, verified 2026-09-28: every storable quality value
(`int` in signed 64-bit range, finite `float`, surrogate-free `str`, including `-5`, `-1.5`,
`-0.0`, `""`) decodes equal to what was encoded and of the same Python type.
