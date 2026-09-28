# Contract: Save Format v1 (`ravel.app.saves`)

**2026-09-28 revision, approved by David** ("make the save independent of the rulebook, and a
change to the rules intertwined with the current stack survivable"): saves no longer carry a
story identity or an `offered` list, and decoding is now **story-free** — `decode_save` takes
only bytes. Resolving saved frames against a (possibly changed) story is `engine.resume`'s job
(engine-api.md), and it never refuses a load on that account. Still format version 1; nothing has
shipped, so nothing bumps.

```python
SAVE_FORMAT: Final = "ravel-save"
SAVE_FORMAT_VERSION: Final = 1
MAX_SAVE_BYTES: Final = 1_048_576  # 1 MiB
SAVE_MAGIC: Final = b'{"format":"ravel-save"'  # every canonical v1 save starts with this


def encode_save(story: Story, state: GameState) -> bytes: ...
def decode_save(data: bytes) -> SavedGame: ...  # raises LoadRefusedError subclasses; no `story` arg
```

Both pure (stdlib `json` only). `encode_save` still takes `story` — it needs to look up each
frame's situation to compute its `Anchor` (see data-model.md § Choice blocks, anchors, and saved
frames). `decode_save` needs no story at all: it only parses and shape-checks; it does not know
or care whether any saved location exists. Field table, canonical encoding, and example: see
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
| 4 | exact key sets and types for `state` and each nested object (`{"qualities","stack","status","outcome"}` — no `story_id`, no `offered`); `bool` refused wherever an int is expected (`anchor.ordinal`); quality names and values pass `Qualities` validation (finite float, int in signed 64-bit range, str with no lone surrogate); each `stack[*].anchor.choices` is a non-empty array of str; `status` ∈ `{"waiting_input", "halted"}`; `outcome` non-null iff `status == "halted"` iff `stack == []` | `SaveCorruptError("<path>: <problem>")` |
| 5 | shape-level (story-free) stack consistency: for consecutive frames, `stack[i+1].location ∈ stack[i].anchor.choices` | `SaveCorruptError("stack[<i>]: <location> is not one of the parent frame's offered choices")` |
| — | any other exception raised during 1–5 | `SaveCorruptError` (chained) — `decode_save` raises **only** `LoadRefusedError` subclasses |

There is deliberately **no** step that checks a location exists in any story, and no step that
checks an outcome label against the story's `End` labels — `decode_save` doesn't have a story to
check against, by design. `GameSession.load` always follows a successful `decode_save` with
`engine.resume(story, saved)`, which is where any actual drift between the save and the current
story shows up (as truncation + a `StoryChanged` output), never as a refusal.

Version is still checked before shape (a v2 file's shape may mean something else). There is no
"identity before shape" step any more — there is no identity.

## Round-trip laws (tested)

- **Unchanged story**: `engine.resume(story, decode_save(encode_save(story, s))).outputs` carries
  no `StoryChanged`, and `encode_save(story, engine.resume(story, decode_save(encode_save(story,
  s))).state) == encode_save(story, s)` for every resting state reachable in Cloak (hypothesis,
  US6-AS3); byte comparison, not `==`.
- Continuing from the resumed state yields identical outputs and a byte-identical final save, for
  an unchanged story.
- JSON `1` decodes to `int`, `1.0` to `float`; `true`, `null`, arrays, and objects are refused as
  quality values.
- **Changed story** (new US4 scenarios, replacing the old "refused" AS4): a benign edit elsewhere
  in the story (lines added/removed above or below the saved choice block) resumes at the same
  menu with **no** `StoryChanged`; deleting the saved situation truncates to the top-level query
  menu with a `StoryChanged` naming it; changing that block's choice set truncates to the parent
  frame's menu with a `StoryChanged`; two identical choice blocks in one situation are
  disambiguated by `ordinal`.

## Examples

```text
b'{"format":"ravel-save","format_version":2,...}'  → UnsupportedSaveVersionError: unsupported save format version 2 (this ravel reads 1)
b'not json'  → SaveCorruptError: not valid JSON: Expecting value: line 1 column 1 (char 0)
b'{"format":"ravel-save","format_version":1,"format_version":2,...}'  → SaveCorruptError: duplicate key 'format_version'
b'{..."qualities":{"Bar":NaN}...}'  → SaveCorruptError: not valid JSON: NaN/Infinity not allowed
b'{..."stack":[{"location":"begin::intro","anchor":{"choices":["begin::intro::press-onward"],"ordinal":0}},{"location":"nowhere","anchor":{"choices":["x"],"ordinal":0}}]...}'  → SaveCorruptError: stack[1]: 'nowhere' is not one of the parent frame's offered choices
b'[' * 100_000  → SaveCorruptError: not valid JSON: maximum recursion depth exceeded
b'{..."qualities":{"Location":"\udc80"}...}'  → SaveCorruptError: state.qualities['Location']: string contains a lone surrogate  (a valid pair escape such as "😀" is accepted)
```

A save naming a location the *current* story doesn't have (e.g. `"nowhere::not-a-place"` as a
frame's own `location`, not a stack-consistency mismatch) is **not** a decode error at all — it
loads fine (`decode_save` has no story to check against) and is truncated by `engine.resume`. See
session-api.md's example for the truncation + `StoryChanged` flow end to end.
