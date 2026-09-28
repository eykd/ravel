"""Immutable game state: qualities, the situation stack, status, and outcome."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from attrs import frozen

type QualityValue = int | float | str
type LocationId = str

QUALITY_TYPES: Final = (int, float, str)
INT_QUALITY_RANGE: Final = range(-(2**63), 2**63)


@frozen
class Qualities:
    """An immutable quality map, stored as name-sorted, name-unique pairs."""

    items: tuple[tuple[str, QualityValue], ...] = ()

    def __attrs_post_init__(self) -> None:
        raise NotImplementedError

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, QualityValue]) -> Qualities:
        """Build qualities from a mapping of names to values."""
        raise NotImplementedError

    def get(self, name: str) -> QualityValue | None:
        """Return the value of ``name``, or ``None`` when it is unset."""
        raise NotImplementedError

    def set(self, name: str, value: QualityValue) -> Qualities:
        """Return new qualities with ``name`` set to a validated ``value``."""
        raise NotImplementedError

    def as_dict(self) -> dict[str, QualityValue]:
        """Return a fresh dict of the qualities."""
        raise NotImplementedError


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
