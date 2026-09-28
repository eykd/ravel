"""The read-only compiled story an engine plays."""

from collections.abc import Mapping
from typing import Self

from attrs import field, frozen

from ravel import types
from ravel.engine.state import LocationId


def _situation_locations(rulebook: types.CompiledRulebook) -> Mapping[str, object]:
    ruleset = rulebook["rulebook"].get("Situation")
    return {} if ruleset is None else ruleset["locations"]


@frozen
class Story:
    """A compiled rulebook, shared read-only between games.

    **2026-09-28 revision, approved by David.** Saves are now independent of the rulebook: they
    carry no story identity, and a load is never refused for "the story changed" (see
    contracts/save-format.md and ``engine.resume`` in contracts/engine-api.md).
    """

    rulebook: types.CompiledRulebook = field(eq=False)

    @classmethod
    def from_rulebook(cls, rulebook: types.CompiledRulebook) -> Self:
        """Wrap ``rulebook``."""
        return cls(rulebook=rulebook)

    def _locations(self) -> Mapping[str, object]:
        return _situation_locations(self.rulebook)

    def situation(self, location: LocationId) -> types.Situation:
        """Return the situation at ``location``; ``KeyError`` if there is none."""
        found = self._locations().get(location)
        if not isinstance(found, types.Situation):
            raise KeyError(location)
        return found

    def has_location(self, location: LocationId) -> bool:
        """Return whether ``location`` names a situation."""
        return isinstance(self._locations().get(location), types.Situation)

    @property
    def givens(self) -> tuple[types.Operation, ...]:
        """Return the story's initial quality operations, in order."""
        return tuple(self.rulebook["givens"])
