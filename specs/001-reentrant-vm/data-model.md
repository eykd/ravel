# Data Model: Re-entrant VM (001)

All domain values are `attrs.frozen` (slots, eq, hashable) unless stated. Module paths are under
`src/ravel/`.

## Scalars (`engine/state.py`)

```python
type QualityValue = int | float | str  # never bool, never NaN/±inf, ints in [-(2**63), 2**63), strs surrogate-free
type LocationId = str  # e.g. "begin::intro::press-onward"

QUALITY_TYPES: Final = (int, float, str)  # runtime check; PEP 695 aliases can't be used with isinstance
INT_QUALITY_RANGE: Final = range(-(2**63), 2**63)
```

## Qualities

```python
@frozen
class Qualities:
    items: tuple[tuple[str, QualityValue], ...] = ()  # sorted by name, unique names

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, QualityValue]) -> Qualities: ...
    def get(self, name: str) -> QualityValue | None: ...  # None = unset (reads as 0 in predicates/ops)
    # set() validates the value; the name and any str value must be surrogate-free (UTF-8 encodable)
    def set(self, name: str, value: QualityValue) -> Qualities: ...
    def as_dict(self) -> dict[str, QualityValue]: ...  # fresh dict each call
```

Invariant: `items` sorted and unique (enforced in `__attrs_post_init__`), so equal maps are equal
values and serialize identically.

## Frame

```python
@frozen
class Frame:
    location: LocationId
    ip: int  # index into Situation.directives; >= 0
```

`ip == len(directives)` means "finished, pop next step". While waiting inside a situation, the
top frame's `ip` points at its `GetChoice` directive (YIELD does not advance, VM spec §4.5).

**Frame is runtime-only.** A save never stores a raw `ip` (2026-09-28 revision, approved by
David — "make the save independent of the rulebook, and a change to the rules intertwined with
the current stack survivable"). Saves store `SavedFrame`s (below); `engine.resume` turns those
back into real `Frame`s against whatever story is loaded, tolerating drift.

## Choice blocks, anchors, and saved frames (`engine/state.py`)

```python
@frozen
class ChoiceBlock:
    choices: tuple[LocationId, ...]  # Choice targets, source order; never empty
    get_choice_ip: int  # index of this block's GetChoice in its situation's directives


def choice_blocks(situation: types.Situation) -> tuple[ChoiceBlock, ...]:
    """Every choice block in ``situation``, source order. Shared by the run loop (``begin_choices``),
    ``encode_save`` (to compute an anchor), and ``engine.resume`` (to resolve one)."""
```

A save can only be taken while `WAITING` (query mode, or parked on a `GetChoice`), so every frame
that needs saving is, by construction, sitting at some choice block. Instead of that block's raw
`ip`, a save names the block by its **content**: the ordered tuple of locations it offers, plus
an ordinal disambiguating two identical blocks in one situation.

```python
@frozen
class Anchor:
    choices: tuple[LocationId, ...]  # the choice block's Choice targets, source order
    ordinal: int  # 0-based: this is the ordinal-th block in the situation with this exact tuple


@frozen
class SavedFrame:
    location: LocationId
    anchor: Anchor


@frozen
class SavedGame:
    """What ``decode_save`` produces: parsed and shape-checked, but not yet resolved against a
    story. ``engine.resume(story, saved)`` does the resolution and is the only consumer."""

    qualities: Qualities
    stack: tuple[SavedFrame, ...]  # bottom -> top; () when status is HALTED
    status: Status  # never RUNNING
    outcome: Outcome | None  # set iff HALTED
```

**Computing an anchor at save time** (`encode_save`): for a runtime `Frame(location, ip)`, find
`get_choice_ip` (the frame's own ip if it is the top of the stack — YIELD does not advance — or
`ip - 1` for every frame below the top, since `choose` advances a parent past its `GetChoice`
before pushing the child, PD-04). Look up `choice_blocks(situation)`, find the block whose
`get_choice_ip` matches, and set `anchor.choices` to that block's `choices` and `anchor.ordinal`
to how many blocks with that exact same `choices` tuple precede it in the situation.

**Resolving an anchor on load** (`engine.resume`, walking bottom -> top): look up the frame's
`location` in the *current* story. Missing -> truncate this frame and every frame above it.
Otherwise scan `choice_blocks(situation)` for every block whose `choices` tuple equals
`anchor.choices`. No match -> truncate here too. Otherwise take the `ordinal`-th match, or the
first match if `ordinal` is out of range (a block was removed but an identical twin remains).
Never raise for this — a changed story degrades the save, it does not refuse it (FR-024).

## Status and Outcome

## Status and Outcome

```python
class Status(StrEnum):
    RUNNING = "running"  # only inside an engine call; never returned, never saved
    WAITING = "waiting_input"
    HALTED = "halted"


@frozen
class Outcome:
    label: str  # author's `end` label verbatim (stripped); "" for bare `- end:` and dead ends
    dead_end: bool = False  # True only when a query matched nothing (FR-012)
```

## GameState (aggregate)

```python
@frozen
class GameState:
    qualities: Qualities
    stack: tuple[Frame, ...]  # bottom → top
    status: Status
    offered: tuple[LocationId, ...]  # display order; () unless WAITING
    outcome: Outcome | None  # set iff HALTED
```

Invariants a *running* `GameState` always satisfies (a property of the run loop, not something
separately checked — `validate_resumable`, which used to check this on every loaded save, is
**removed** as of 2026-09-28: a loaded save is resolved by `engine.resume`'s anchor-based
truncation instead, which cannot produce a stack violating these, by construction):

| Status | stack | offered | outcome |
|---|---|---|---|
| `WAITING`, query menu | `()` | non-empty; equals the re-derived query menu | `None` |
| `WAITING`, in-situation | non-empty; every frame location is a `Situation`; the bottom frame is a `Situation` rule; every non-top frame has `directives[ip-1]` a `GetChoice` and the frame above it is one of that block's `Choice` locations; top `ip` → a `GetChoice` | non-empty; equals the top block's `Choice` locations in source order | `None` |
| `HALTED` | `()` | `()` | set; `dead_end` with `label == ""`, or any other `label` (2026-09-28: no longer checked against `story.end_labels` — see contracts/end-directive.md § Save validation) |
| `RUNNING` | never valid at rest | | |

State transitions:

```text
            start(story)                         choose(loc)
  (none) ───────────────► WAITING ◄──────────────────────────┐
                            │  choose(loc) → run until yield  │
                            ├─────────────────────────────────┘
                            │  run reaches `end` or query finds nothing
                            ▼
                          HALTED  (terminal: choose → GameOverError)
```

## Story (`engine/story.py`)

```python
@frozen
class Story:
    rulebook: CompiledRulebook = field(eq=False)  # Environment.load() result; read-only; eq/hash via identity
    identity: str  # "sha256:<64 hex>" — no longer read by the save/load path (2026-09-28)

    @classmethod
    def from_rulebook(cls, rulebook: CompiledRulebook) -> Story: ...  # computes identity
    def situation(self, location: LocationId) -> types.Situation: ...  # KeyError → caller maps to error
    def has_location(self, location: LocationId) -> bool: ...
    @property
    def givens(self) -> tuple[types.Operation, ...]: ...
```

**2026-09-28 revision, approved by David.** Saves are now independent of the rulebook: they carry
no story identity, and a load is never refused for "the story changed" (see Save file below and
`resume` in engine-api.md). `identity`/`fingerprint`/`IR_VERSION` and `Story.end_labels`/
`_collect_end_labels` had exactly one consumer each — the old save format — and none remain. They
are **dead code once the US4 Green leaf lands** and should be deleted then (`identity` and
`fingerprint()` from `story.py`, `end_labels`/`_collect_end_labels`, `IR_VERSION`), along with
`tests/engine/test_story.py`'s fingerprint/identity-stability tests (path/whitespace/
`PYTHONHASHSEED` independence) — those properties no longer matter to anything. `fingerprint`
encoded `{"ir": IR_VERSION, "rulebook": ..., "givens": [...]}` with a canonical encoder (attrs
instances → `{"type": ClassName, **fields}`, the `types.VALUE` sentinel → `{"type": "VALUE"}`,
`str`/`bool`/`int`/`float`/`None` as-is, tuples/lists → lists, `Mapping` with `str` keys → sorted
object) then SHA-256; this description is kept here only as a record of what's being removed.

`types.py` additions: `CompiledRulebook(TypedDict)` = `{"metadata": dict[str, str], "rulebook":
dict[str, Ruleset], "givens": list[Operation]}`, `Ruleset(TypedDict)` = `{"rules": list[Rule],
"locations": dict[str, object]}` (non-`Situation` concepts store lists of strings;
`Story.situation()` narrows with `isinstance`), and `End(outcome: str)`. `Rule`, `Predicate`, and
`Comparison` keep `order=True` (the compiler sorts them).

## Outputs (`engine/outputs.py`)

Plain data only: `str`, `int`, `float`, `bool`, `None`, and tuples of frozen values. No state
references, no callables (FR-007).

```python
@frozen
class TextShown:
    text: str
    sticky: bool = False


@frozen
class ChoiceOption:
    location: LocationId
    label: str


@frozen
class ChoicesOffered:
    choices: tuple[ChoiceOption, ...]  # never empty


@frozen
class QualityChanged:
    name: str
    old: QualityValue | None
    new: QualityValue


@frozen
class SituationEntered:
    location: LocationId


@frozen
class SituationExited:
    location: LocationId


@frozen
class Halted:
    outcome: str
    dead_end: bool


@frozen
class StoryChanged:
    """Emitted by ``engine.resume`` when the loaded story no longer matches one or more saved
    frames and they were truncated (2026-09-28). Never emitted on a fresh ``start``/``choose``,
    and never emitted by a load against an unchanged story."""

    dropped: tuple[LocationId, ...]  # the dropped frames' locations, bottom (deepest kept) to top


type Output = TextShown | ChoicesOffered | QualityChanged | SituationEntered | SituationExited | Halted | StoryChanged


@frozen
class Step:
    state: GameState
    outputs: tuple[Output, ...]
```

`ChoiceOption.label` is `Situation.intro.text` of the offered location (the `[bracketed]`
head+suffix form), for both query and in-situation menus.

## Save file (snapshot), format version 1

**2026-09-28 revision, approved by David: "make the save independent of the rulebook, and a
change to the rules intertwined with the current stack survivable."** A save no longer carries a
story identity and no longer carries `offered` (both dropped). Frames are saved as `location` +
`anchor`, never a raw `ip`. Nothing here bumps `format_version` — nothing has shipped yet.

Canonical bytes = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False).encode("utf-8") + b"\n"`.

```json
{"format":"ravel-save","format_version":1,"state":{"outcome":null,"qualities":{"Location":"Intro","Wearing Cloak":1},"stack":[{"anchor":{"choices":["begin::intro::press-onward"],"ordinal":0},"location":"begin::intro"}],"status":"waiting_input"}}
```

| Field | Type | Rule |
|---|---|---|
| `format` | `"ravel-save"` | exact |
| `format_version` | int | `== 1`, else `UnsupportedSaveVersionError` (bool rejected) |
| `state.qualities` | object str → int/float/str | JSON int stays int, JSON float (`1.0`) stays float; bool/null/array rejected; names and str values containing a lone surrogate (U+D800–U+DFFF, e.g. from a `\udc80` escape) rejected, so every loaded state re-encodes |
| `state.stack` | array of `{"location": str, "anchor": {"choices": [str, ...] (non-empty), "ordinal": int >= 0}}` (bool refused for `ordinal`) | bottom → top; `stack[i+1].location` must be a member of `stack[i].anchor.choices` (shape-level, story-free — see save-format.md); nothing here checks that any `location` exists in a story — that is `engine.resume`'s job, and it never refuses |
| `state.status` | `"waiting_input"` \| `"halted"` | `"running"` refused; `status == "halted"` iff `stack == []` and `outcome` is non-null |
| `state.outcome` | null \| `{"label": str, "dead_end": bool}` | non-null iff halted; **no longer checked against the story's `End` labels** — a stale or fabricated label just loads as that halt (the load-refusal threat model only guards against a save crashing or soft-locking the engine, not against a player editing their own save, plan.md § Security Considerations) |

Removed fields: `story_id` (dropped entirely — no story-identity check exists anywhere on the
load path) and `state.offered` (menus are always re-derived from the current story + qualities,
never stored).

Extra unknown keys and duplicate keys are refused (`SaveCorruptError`); `NaN`/`Infinity` literals
are refused; the whole file is capped at `MAX_SAVE_BYTES` (1 MiB). Every canonical v1 save starts
with `SAVE_MAGIC = b'{"format":"ravel-save"'` (used by the `FileSaveStore` clobber guard).

## Session (`app/session.py`)

`GameSession(story: Story, saves: SaveStore)` holds the one mutable reference: `state:
GameState | None` (None before `new_game`/`load`). All transitions replace it atomically, only
after the engine or decoder succeeded (FR-015, FR-024). `load` is `saves.read` → `decode_save`
(pure JSON parse, story-free) → `engine.resume(story, saved)` (pure, never refuses) → assign →
return `resume`'s outputs verbatim (a leading `StoryChanged` when frames were dropped, then the
re-presented menu or halt).
