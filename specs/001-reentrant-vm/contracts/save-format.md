# Contract: Save Format v1 (`ravel.app.saves`)

```python
SAVE_FORMAT: Final = "ravel-save"
SAVE_FORMAT_VERSION: Final = 1


def encode_save(story: Story, state: GameState) -> bytes: ...
def decode_save(story: Story, data: bytes) -> GameState: ...  # raises LoadRefusedError subclasses
```

Pure (stdlib `json` only). Field table, canonical encoding, and example: see
[data-model.md § Save file](../data-model.md#save-file-snapshot-format-version-1).

## Encoding

`json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
UTF-8, plus a trailing `\n`. `encode_save(story, s1) == encode_save(story, s2)` iff `s1 == s2`
(FR-022, FR-025). Encoding a `RUNNING` state raises `InvalidStateError` (never happens via the
engine).

## Decoding order (first failure wins; nothing is assigned on failure)

| # | Check | Error |
|---|---|---|
| 1 | UTF-8 + `json.loads` succeeds, top level is an object | `SaveCorruptError("not valid JSON: <msg>")` |
| 2 | `format == "ravel-save"` | `SaveCorruptError("not a ravel save file")` |
| 3 | `format_version` present, an `int` (not bool), `== 1` | `UnsupportedSaveVersionError(<value>)` |
| 4 | `story_id == story.identity` | `StoryChangedError` |
| 5 | exact key sets and types for `state` and each nested object | `SaveCorruptError("<path>: <problem>")` |
| 6 | every `stack[*].location` and `offered[*]` exists in `story` | `UnknownLocationError(<location>)` |
| 7 | `engine.validate_resumable(story, state)` | `SaveCorruptError` (chained `InvalidStateError`) |

Version checked before identity (a v2 file's identity field may mean something else); identity
before shape (the most useful message for the common "I edited my story" case).

## Round-trip laws (tested)

- `decode_save(story, encode_save(story, s)) == s` for every resting state reachable in Cloak
  (hypothesis, US6-AS3).
- Continuing from the decoded state yields identical outputs and a byte-identical final save.
- JSON `1` decodes to `int`, `1.0` to `float`; `true`, `null`, arrays, and objects are refused as
  quality values.

## Examples

```text
b'{"format":"ravel-save","format_version":2,...}'  → UnsupportedSaveVersionError: unsupported save format version 2 (this ravel reads 1)
b'{"format":"ravel-save","format_version":1,"story_id":"sha256:00…",...}'  → StoryChangedError
b'{"format":"ravel-save","format_version":1,"story_id":<ok>,"state":{"stack":[{"location":"nowhere","ip":0}],...}}'  → UnknownLocationError: nowhere
b'not json'  → SaveCorruptError: not valid JSON: Expecting value: line 1 column 1 (char 0)
```
