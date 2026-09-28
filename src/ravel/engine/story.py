"""The read-only compiled story an engine plays, and its stable content identity."""

from typing import Final, Self

from attrs import field, frozen

from ravel import types
from ravel.engine.state import LocationId

IR_VERSION: Final = 1


def fingerprint(rulebook: types.CompiledRulebook) -> str:
    """Return the ``sha256:`` content identity of ``rulebook``."""
    raise NotImplementedError


@frozen
class Story:
    """A compiled rulebook plus its identity; shared read-only between games."""

    rulebook: types.CompiledRulebook = field(eq=False)
    identity: str
    end_labels: frozenset[str]

    @classmethod
    def from_rulebook(cls, rulebook: types.CompiledRulebook) -> Self:
        """Wrap ``rulebook``, computing its identity and end labels."""
        raise NotImplementedError

    def situation(self, location: LocationId) -> types.Situation:
        """Return the situation at ``location``; ``KeyError`` if there is none."""
        raise NotImplementedError

    def has_location(self, location: LocationId) -> bool:
        """Return whether ``location`` names a situation."""
        raise NotImplementedError

    @property
    def givens(self) -> tuple[types.Operation, ...]:
        """Return the story's initial quality operations, in order."""
        raise NotImplementedError
