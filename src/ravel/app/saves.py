"""Save format v1: canonical, rulebook-independent JSON encode/decode.

**2026-09-28 revision, approved by David** ("make the save independent of the rulebook, and a
change to the rules intertwined with the current stack survivable"): saves no longer carry a
story identity or an ``offered`` list. ``encode_save`` still takes a ``story`` -- it needs to look
up each frame's situation to compute its ``Anchor`` -- but ``decode_save`` is story-free: it only
parses and shape-checks bytes. Resolving saved frames against a (possibly changed) story is
``engine.resume``'s job (see contracts/engine-api.md), and it never refuses a load on that
account. See contracts/save-format.md and data-model.md SS Save file for the full contract.
"""

import json
import math
from collections.abc import Mapping
from typing import Final

from ravel.engine.engine import choice_blocks
from ravel.engine.errors import InvalidStateError
from ravel.engine.state import (
    INT_QUALITY_RANGE,
    Anchor,
    Frame,
    GameState,
    Outcome,
    Qualities,
    QualityValue,
    SavedFrame,
    SavedGame,
    Status,
)
from ravel.engine.story import Story

SAVE_FORMAT: Final = "ravel-save"
SAVE_FORMAT_VERSION: Final = 1
MAX_SAVE_BYTES: Final = 1_048_576  # 1 MiB
SAVE_MAGIC: Final = b'{"format":"ravel-save"'  # every canonical v1 save starts with this


class SessionError(Exception):
    """Base class for every error a ``GameSession`` raises."""


class NoGameError(SessionError):
    """No game has been started or loaded yet."""


class LoadRefusedError(SessionError):
    """Base class for every reason ``decode_save`` (or a session's ``load``) refuses a save."""


class SaveNotFoundError(LoadRefusedError):
    """No save file exists at the given name."""


class SaveUnreadableError(LoadRefusedError):
    """The save file exists but could not be read."""


class SaveCorruptError(LoadRefusedError):
    """The save file's bytes are not a valid, well-shaped save."""


class UnsupportedSaveVersionError(LoadRefusedError):
    """The save names a ``format_version`` this ravel cannot read."""

    def __init__(self, version: object) -> None:
        super().__init__("unsupported save format version %r (this ravel reads %d)" % (version, SAVE_FORMAT_VERSION))
        self.version = version


def _is_surrogate_free(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


# --- encoding ---------------------------------------------------------------------------------


def _anchor_for(story: Story, frame: Frame, *, is_top: bool) -> Anchor:
    """Compute the ``Anchor`` naming the choice block ``frame`` is parked at.

    For the top frame, ``ip`` already points at the block's ``GetChoice`` (YIELD does not
    advance). For every frame below the top, ``choose`` advanced it past its ``GetChoice`` before
    pushing the child (PD-04), so the block's ``get_choice_ip`` is ``ip - 1``.
    """
    get_choice_ip = frame.ip if is_top else frame.ip - 1
    situation = story.situation(frame.location)
    blocks = choice_blocks(situation)
    for index, block in enumerate(blocks):
        if block.get_choice_ip == get_choice_ip:
            ordinal = sum(1 for earlier in blocks[:index] if earlier.choices == block.choices)
            return Anchor(choices=block.choices, ordinal=ordinal)
    raise InvalidStateError("%r has no choice block at ip %d" % (frame.location, get_choice_ip))


def _saved_frame(story: Story, frame: Frame, *, is_top: bool) -> SavedFrame:
    return SavedFrame(location=frame.location, anchor=_anchor_for(story, frame, is_top=is_top))


def _outcome_doc(outcome: Outcome | None) -> dict[str, object] | None:
    if outcome is None:
        return None
    return {"label": outcome.label, "dead_end": outcome.dead_end}


def _frame_doc(frame: SavedFrame) -> dict[str, object]:
    return {
        "location": frame.location,
        "anchor": {"choices": list(frame.anchor.choices), "ordinal": frame.anchor.ordinal},
    }


def encode_save(story: Story, state: GameState) -> bytes:
    """Encode ``state`` (waiting or halted) as canonical save bytes.

    Raises ``InvalidStateError`` for a ``RUNNING`` state (never happens via the engine).
    """
    if state.status is Status.RUNNING:
        raise InvalidStateError("cannot save a running state")
    last = len(state.stack) - 1
    saved_stack = [_saved_frame(story, frame, is_top=(index == last)) for index, frame in enumerate(state.stack)]
    doc = {
        "format": SAVE_FORMAT,
        "format_version": SAVE_FORMAT_VERSION,
        "state": {
            "qualities": state.qualities.as_dict(),
            "stack": [_frame_doc(frame) for frame in saved_stack],
            "status": state.status.value,
            "outcome": _outcome_doc(state.outcome),
        },
    }
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


# --- decoding -----------------------------------------------------------------------------------


def _reject_constant(_value: str) -> None:
    raise ValueError("NaN/Infinity not allowed")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: set[str] = set()
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise SaveCorruptError("duplicate key %r" % key)
        seen.add(key)
        result[key] = value
    return result


def _parse_json(data: bytes) -> object:
    try:
        text = data.decode("utf-8")
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_reject_duplicates)
    except SaveCorruptError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise SaveCorruptError("not valid JSON: %s" % error) from error


def _check_keys(obj: Mapping[str, object], required: set[str], label: str) -> None:
    keys = set(obj)
    if keys == required:
        return
    missing = required - keys
    extra = keys - required
    problems = []
    if missing:
        problems.append("missing %s" % ", ".join(sorted(repr(key) for key in missing)))
    if extra:
        problems.append("unexpected %s" % ", ".join(sorted(repr(key) for key in extra)))
    raise SaveCorruptError("%s: %s" % (label, "; ".join(problems)))


def _decode_qualities(raw: object) -> Qualities:
    if not isinstance(raw, dict):
        raise SaveCorruptError("state.qualities: must be an object")
    items: dict[str, QualityValue] = {}
    for name, value in raw.items():
        # ``name`` is always ``str``: JSON object keys can only ever be strings.
        if not _is_surrogate_free(name):
            raise SaveCorruptError("state.qualities: %r is not a valid quality name" % (name,))
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise SaveCorruptError("state.qualities[%r]: must be an int, float, or string" % name)
        if isinstance(value, int) and value not in INT_QUALITY_RANGE:
            raise SaveCorruptError("state.qualities[%r]: int is out of the signed 64-bit range" % name)
        if isinstance(value, float) and not math.isfinite(value):
            raise SaveCorruptError("state.qualities[%r]: float must be finite" % name)
        if isinstance(value, str) and not _is_surrogate_free(value):
            raise SaveCorruptError("state.qualities[%r]: string contains a lone surrogate" % name)
        items[name] = value
    return Qualities.from_mapping(items)


def _decode_anchor(raw: object, path: str) -> Anchor:
    if not isinstance(raw, dict):
        raise SaveCorruptError("%s: must be an object" % path)
    _check_keys(raw, {"choices", "ordinal"}, path)
    choices_raw = raw["choices"]
    if not isinstance(choices_raw, list) or not choices_raw or not all(isinstance(c, str) for c in choices_raw):
        raise SaveCorruptError("%s.choices: must be a non-empty array of strings" % path)
    ordinal = raw["ordinal"]
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise SaveCorruptError("%s.ordinal: must be a non-negative int" % path)
    return Anchor(choices=tuple(choices_raw), ordinal=ordinal)


def _decode_frame(raw: object, index: int) -> SavedFrame:
    path = "state.stack[%d]" % index
    if not isinstance(raw, dict):
        raise SaveCorruptError("%s: must be an object" % path)
    _check_keys(raw, {"location", "anchor"}, path)
    location = raw["location"]
    if not isinstance(location, str):
        raise SaveCorruptError("%s.location: must be a string" % path)
    anchor = _decode_anchor(raw["anchor"], "%s.anchor" % path)
    return SavedFrame(location=location, anchor=anchor)


def _decode_stack(raw: object) -> tuple[SavedFrame, ...]:
    if not isinstance(raw, list):
        raise SaveCorruptError("state.stack: must be an array")
    return tuple(_decode_frame(item, index) for index, item in enumerate(raw))


def _decode_status(raw: object) -> Status:
    if raw not in (Status.WAITING.value, Status.HALTED.value):
        raise SaveCorruptError("state.status: must be 'waiting_input' or 'halted'")
    return Status(raw)


def _decode_outcome(raw: object, *, halted: bool) -> Outcome | None:
    if raw is None:
        if halted:
            raise SaveCorruptError("state.outcome: required when halted")
        return None
    if not halted:
        raise SaveCorruptError("state.outcome: must be null unless halted")
    if not isinstance(raw, dict):
        raise SaveCorruptError("state.outcome: must be an object or null")
    _check_keys(raw, {"label", "dead_end"}, "state.outcome")
    label = raw["label"]
    if not isinstance(label, str):
        raise SaveCorruptError("state.outcome.label: must be a string")
    dead_end = raw["dead_end"]
    if not isinstance(dead_end, bool):
        raise SaveCorruptError("state.outcome.dead_end: must be a bool")
    return Outcome(label=label, dead_end=dead_end)


def _check_stack_consistency(stack: tuple[SavedFrame, ...]) -> None:
    for i in range(len(stack) - 1):
        parent, child = stack[i], stack[i + 1]
        if child.location not in parent.anchor.choices:
            raise SaveCorruptError(
                "stack[%d]: %r is not one of the parent frame's offered choices" % (i + 1, child.location)
            )


def _decode_save(data: bytes) -> SavedGame:
    if len(data) > MAX_SAVE_BYTES:
        raise SaveCorruptError("save file too large (over 1 MiB)")

    doc = _parse_json(data)
    if not isinstance(doc, dict):
        raise SaveCorruptError("not valid JSON: top-level value must be an object")

    if doc.get("format") != SAVE_FORMAT:
        raise SaveCorruptError("not a ravel save file")

    version = doc.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise SaveCorruptError("format_version: must be an int")
    if version != SAVE_FORMAT_VERSION:
        raise UnsupportedSaveVersionError(version)

    _check_keys(doc, {"format", "format_version", "state"}, "top level")

    state_doc = doc["state"]
    if not isinstance(state_doc, dict):
        raise SaveCorruptError("state: must be an object")
    _check_keys(state_doc, {"qualities", "stack", "status", "outcome"}, "state")

    qualities = _decode_qualities(state_doc["qualities"])
    stack = _decode_stack(state_doc["stack"])
    status = _decode_status(state_doc["status"])
    halted = status is Status.HALTED
    if halted and stack != ():
        raise SaveCorruptError("state.stack: must be empty when status is 'halted'")
    outcome = _decode_outcome(state_doc["outcome"], halted=halted)

    _check_stack_consistency(stack)

    return SavedGame(qualities=qualities, stack=stack, status=status, outcome=outcome)


def decode_save(data: bytes) -> SavedGame:
    """Parse and shape-check ``data``, raising only ``LoadRefusedError`` subclasses.

    Story-free: this never checks that any saved ``location`` exists in any story. That is
    ``engine.resume``'s job, and it never refuses a load on that account.
    """
    try:
        return _decode_save(data)
    except LoadRefusedError:
        raise
    except Exception as error:
        raise SaveCorruptError("unexpected error decoding save: %s" % error) from error
