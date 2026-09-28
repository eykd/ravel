"""The pure run loop: ``start`` a new game and ``choose`` among offered choices."""

from ravel.engine.outputs import Step
from ravel.engine.state import GameState, LocationId
from ravel.engine.story import Story


def start(story: Story) -> Step:
    """Apply ``story``'s givens once each, then run to the first menu or halt."""
    raise NotImplementedError


def choose(story: Story, state: GameState, location: LocationId) -> Step:
    """Enter the offered ``location`` from a waiting ``state`` and run to the next wait or halt."""
    raise NotImplementedError
