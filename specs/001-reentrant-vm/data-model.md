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

Invariants (checked by `engine.validate_resumable(story, state)`, used by save loading):

| Status | stack | offered | outcome |
|---|---|---|---|
| `WAITING`, query menu | `()` | non-empty; equals the re-derived query menu | `None` |
| `WAITING`, in-situation | non-empty; every frame location is a `Situation`; the bottom frame is a `Situation` rule; every non-top frame has `directives[ip-1]` a `GetChoice` and the frame above it is one of that block's `Choice` locations; top `ip` → a `GetChoice` | non-empty; equals the top block's `Choice` locations in source order | `None` |
| `HALTED` | `()` | `()` | set; `label ∈ story.end_labels`, or `dead_end` with `label == ""` |
| `RUNNING` | never valid at rest → `InvalidStateError` | | |

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
    identity: str  # "sha256:<64 hex>"
    end_labels: frozenset[str]  # every compiled End.outcome; validates halted saves

    @classmethod
    def from_rulebook(cls, rulebook: CompiledRulebook) -> Story: ...  # computes identity
    def situation(self, location: LocationId) -> types.Situation: ...  # KeyError → caller maps to error
    def has_location(self, location: LocationId) -> bool: ...
    @property
    def givens(self) -> tuple[types.Operation, ...]: ...


IR_VERSION: Final = 1  # bump when compiled-directive semantics change; folded into identity


def fingerprint(rulebook: CompiledRulebook) -> str: ...
```

`fingerprint` encodes `{"ir": IR_VERSION, "rulebook": <all concepts: sorted rules as
[name, [predicates]], locations as {id: situation}>, "givens": [...]}` with a canonical encoder
(attrs instances → `{"type": ClassName, **fields}` iterating `attrs.fields(type(obj))`, so class
attributes such as `_comparators` are excluded and `repr=False` fields such as `Text.predicate`
are included; the `types.VALUE` sentinel — a **class** object, `parsers.visit_qvalue` returns
`types.VALUE` itself — → `{"type": "VALUE"}`; `str` and `str` subclasses → `str`; `bool`/`int`/
`float`/`None` as-is; tuples/lists → lists; `Mapping` with `str` keys → object, keys sorted),
then `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` →
SHA-256. **Any other type raises `TypeError`** — no `repr`/`str` fallback. In particular syml
1.0's `Source` is a frozen dataclass, **not** a `str` subclass, and carries `filename` (an
absolute path) and positions; if one ever reached a compiled value, a fallback would make the
identity path- and whitespace-dependent. Sets are refused (their order varies with
`PYTHONHASHSEED`). `metadata` (`about:`) and source positions are excluded.

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


type Output = TextShown | ChoicesOffered | QualityChanged | SituationEntered | SituationExited | Halted


@frozen
class Step:
    state: GameState
    outputs: tuple[Output, ...]
```

`ChoiceOption.label` is `Situation.intro.text` of the offered location (the `[bracketed]`
head+suffix form), for both query and in-situation menus.

## Save file (snapshot), format version 1

Canonical bytes = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False).encode("utf-8") + b"\n"`.

```json
{"format":"ravel-save","format_version":1,"state":{"offered":["begin::intro::press-onward"],"outcome":null,"qualities":{"Location":"Intro","Wearing Cloak":1},"stack":[{"ip":4,"location":"begin::intro"}],"status":"waiting_input"},"story_id":"sha256:…"}
```

| Field | Type | Rule |
|---|---|---|
| `format` | `"ravel-save"` | exact |
| `format_version` | int | `== 1`, else `UnsupportedSaveVersionError` (bool rejected) |
| `story_id` | str | `== story.identity`, else `StoryChangedError` |
| `state.qualities` | object str → int/float/str | JSON int stays int, JSON float (`1.0`) stays float; bool/null/array rejected; names and str values containing a lone surrogate (U+D800–U+DFFF, e.g. from a `\udc80` escape) rejected, so every loaded state re-encodes |
| `state.stack` | array of `{"location": str, "ip": int >= 0}` (bool refused) | bottom → top; locations must exist; whole-stack invariants above |
| `state.status` | `"waiting_input"` \| `"halted"` | `"running"` refused |
| `state.offered` | array of str | locations must exist; must equal the re-derived menu |
| `state.outcome` | null \| `{"label": str, "dead_end": bool}` | non-null iff halted; label ∈ `story.end_labels` (or `""` with `dead_end`) |

Extra unknown keys and duplicate keys are refused (`SaveCorruptError`); `NaN`/`Infinity` literals
are refused; the whole file is capped at `MAX_SAVE_BYTES` (1 MiB). Every canonical v1 save starts
with `SAVE_MAGIC = b'{"format":"ravel-save"'` (used by the `FileSaveStore` clobber guard).

## Session (`app/session.py`)

`GameSession(story: Story, saves: SaveStore)` holds the one mutable reference: `state:
GameState | None` (None before `new_game`/`load`). All transitions replace it atomically, only
after the engine or decoder succeeded (FR-015, FR-024).
