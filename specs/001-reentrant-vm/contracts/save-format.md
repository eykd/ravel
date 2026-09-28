# Contract: Save Format v1 (`ravel.app.saves`)

```python
SAVE_FORMAT: Final = "ravel-save"
SAVE_FORMAT_VERSION: Final = 1
MAX_SAVE_BYTES: Final = 1_048_576  # 1 MiB
SAVE_MAGIC: Final = b'{"format":"ravel-save"'  # every canonical v1 save starts with this


def encode_save(story: Story, state: GameState) -> bytes: ...
def decode_save(story: Story, data: bytes) -> GameState: ...  # raises LoadRefusedError subclasses
```

Pure (stdlib `json` only). Field table, canonical encoding, and example: see
[data-model.md § Save file](../data-model.md#save-file-snapshot-format-version-1).

## Encoding

`json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
UTF-8, plus a trailing `\n`. Equal bytes ⇒ equal states (FR-022, FR-025). The converse does
**not** hold under Python `==` (`1 == 1.0`, `0.0 == -0.0`), so tests compare bytes, never just
`==`. Encoding a `RUNNING` state raises `InvalidStateError` (never happens via the engine).

## Decoding order (first failure wins; nothing is assigned on failure)

| # | Check | Error |
|---|---|---|
| 0 | `len(data) <= MAX_SAVE_BYTES` | `SaveCorruptError("save file too large (over 1 MiB)")` |
| 1 | strict `data.decode("utf-8")` (BOM refused) + `json.loads(text, parse_constant=reject, object_pairs_hook=reject_duplicates)`; top level is an object. `UnicodeDecodeError`, `ValueError` (incl. `JSONDecodeError`, >4300-digit ints), and `RecursionError` are all caught | `SaveCorruptError("not valid JSON: <msg>")` / `("duplicate key 'x'")` / `("NaN/Infinity not allowed")` |
| 2 | `format == "ravel-save"` | `SaveCorruptError("not a ravel save file")` |
| 3 | `format_version` present, an `int` (not bool), `== 1` | `UnsupportedSaveVersionError(<value>)` |
| 4 | `story_id == story.identity` | `StoryChangedError` |
| 5 | exact key sets and types for `state` and each nested object; `bool` refused wherever an int is expected (`ip`, quality values); quality names and values pass `Qualities` validation (finite float, int in signed 64-bit range, str with no lone surrogate) | `SaveCorruptError("<path>: <problem>")` |
| 6 | every `stack[*].location` and `offered[*]` exists in `story` | `UnknownLocationError(<location>)` |
| 7 | `engine.validate_resumable(story, state)` — whole-stack invariants, offered menu, halted outcome label ∈ story `End` labels | `SaveCorruptError` (chained `InvalidStateError`) |
| — | any other exception raised during 1–7 (e.g. `TypeError` re-deriving a query menu over tampered quality types) | `SaveCorruptError` (chained) — `decode_save` raises **only** `LoadRefusedError` subclasses |

Version checked before identity (a v2 file's identity field may mean something else); identity
before shape (the most useful message for the common "I edited my story" case).

## Round-trip laws (tested)

- `encode_save(story, decode_save(story, encode_save(story, s))) == encode_save(story, s)` for
  every resting state reachable in Cloak (hypothesis, US6-AS3); byte comparison, not `==`.
- Continuing from the decoded state yields identical outputs and a byte-identical final save.
- JSON `1` decodes to `int`, `1.0` to `float`; `true`, `null`, arrays, and objects are refused as
  quality values.

## Examples

```text
b'{"format":"ravel-save","format_version":2,...}'  → UnsupportedSaveVersionError: unsupported save format version 2 (this ravel reads 1)
b'{"format":"ravel-save","format_version":1,"story_id":"sha256:00…",...}'  → StoryChangedError
b'{"format":"ravel-save","format_version":1,"story_id":<ok>,"state":{"stack":[{"location":"nowhere","ip":0}],...}}'  → UnknownLocationError: nowhere
b'not json'  → SaveCorruptError: not valid JSON: Expecting value: line 1 column 1 (char 0)
b'{"format":"ravel-save","format_version":1,"format_version":2,...}'  → SaveCorruptError: duplicate key 'format_version'
b'{..."qualities":{"Bar":NaN}...}'  → SaveCorruptError: not valid JSON: NaN/Infinity not allowed
b'{..."stack":[{"location":"begin::intro","ip":0},{"location":"begin::intro::press-onward","ip":2}]...}'  → SaveCorruptError: stack[0]: ip 0 does not follow a choice block
b'{..."status":"halted","outcome":{"label":"\u001b]52;c;...","dead_end":false}...}'  → SaveCorruptError: outcome label is not an ending this story has
b'[' * 100_000  → SaveCorruptError: not valid JSON: maximum recursion depth exceeded
b'{..."qualities":{"Location":"\udc80"}...}'  → SaveCorruptError: state.qualities['Location']: string contains a lone surrogate  (a valid pair escape such as "\ud83d\ude00" is accepted)
```
