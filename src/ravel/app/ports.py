"""Ports the application layer depends on (contracts/session-api.md).

``ravel.app`` depends on these ``Protocol``s, never on any concrete adapter -- adapters
(``ravel.adapters``) implement them.
"""

from typing import Protocol

from ravel.engine.story import Story


class StorySource(Protocol):
    """Compiles a ``Story`` from wherever it lives."""

    def load(self) -> Story:
        """Compile and return the story; raises ``ravel.exceptions.*`` on a bad source."""
        ...


class SaveStore(Protocol):
    """Reads and writes save bytes by name."""

    def write(self, name: str, data: bytes) -> str:
        """Write ``data`` under ``name`` and return a display path; ``OSError`` propagates."""
        ...

    def read(self, name: str) -> bytes:
        """Read at most ``MAX_SAVE_BYTES + 1`` bytes from ``name``; ``OSError`` propagates."""
        ...
