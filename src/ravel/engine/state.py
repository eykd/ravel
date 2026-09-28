"""Immutable game state: qualities, the situation stack, status, and outcome."""

import math
from collections.abc import Mapping
from enum import StrEnum
from itertools import pairwise
from typing import Final

from attrs import frozen

from ravel.engine.errors import InvalidQualityValueError

type QualityValue = int | float | str
type LocationId = str

QUALITY_TYPES: Final = (int, float, str)
INT_QUALITY_RANGE: Final = range(-(2**63), 2**63)


def _is_surrogate_free(text: str) -> bool:
    """Return whether ``text`` encodes as UTF-8, i.e. holds no lone surrogate."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _is_storable(value: object) -> bool:
    """Return whether ``value`` lies in the storable quality domain."""
    if isinstance(value, bool) or not isinstance(value, QUALITY_TYPES):
        return False
    if isinstance(value, int):
        return value in INT_QUALITY_RANGE
    if isinstance(value, float):
        return math.isfinite(value)
    return _is_surrogate_free(value)


def _validate_quality(name: str, value: object) -> None:
    """Raise ``InvalidQualityValueError`` unless ``name`` and ``value`` are storable."""
    if not _is_surrogate_free(name):
        raise InvalidQualityValueError("Quality name %r holds a lone surrogate" % name)
    if not _is_storable(value):
        raise InvalidQualityValueError("Quality %r has an unstorable value %r" % (name, value))


@frozen
class Qualities:
    """An immutable quality map, stored as name-sorted, name-unique pairs."""

    items: tuple[tuple[str, QualityValue], ...] = ()

    def __attrs_post_init__(self) -> None:
        names = [name for name, _ in self.items]
        if any(first >= second for first, second in pairwise(names)):
            raise ValueError("Quality items must be sorted by name with unique names: %r" % (names,))
        for name, value in self.items:
            _validate_quality(name, value)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, QualityValue]) -> Qualities:
        """Build qualities from a mapping of names to values."""
        return cls(items=tuple(sorted(mapping.items())))

    def get(self, name: str) -> QualityValue | None:
        """Return the value of ``name``, or ``None`` when it is unset."""
        return self.as_dict().get(name)

    def set(self, name: str, value: QualityValue) -> Qualities:
        """Return new qualities with ``name`` set to a validated ``value``."""
        return self.from_mapping({**self.as_dict(), name: value})

    def as_dict(self) -> dict[str, QualityValue]:
        """Return a fresh dict of the qualities."""
        return dict(self.items)


@frozen
class Frame:
    """One situation on the stack and the index of its next directive."""

    location: LocationId
    ip: int


class Status(StrEnum):
    """Where a game stands between engine calls."""

    RUNNING = "running"
    WAITING = "waiting_input"
    HALTED = "halted"


@frozen
class Outcome:
    """How a halted game ended."""

    label: str
    dead_end: bool = False


@frozen
class GameState:
    """The complete, immutable state of a game at rest."""

    qualities: Qualities
    stack: tuple[Frame, ...]
    status: Status
    offered: tuple[LocationId, ...]
    outcome: Outcome | None
