"""The application layer: sessions, ports, and the save format.

Errors are defined in ``ravel.app.saves`` and re-exported here (contracts/session-api.md).
``GameSession`` (``ravel.app.session``) is the session's single mutable holder.
"""

from ravel.app.saves import (
    LoadRefusedError,
    NoGameError,
    SaveCorruptError,
    SaveNotFoundError,
    SaveUnreadableError,
    SessionError,
    UnsupportedSaveVersionError,
)
from ravel.app.session import DEFAULT_SAVE_NAME, GameSession

__all__ = [
    "DEFAULT_SAVE_NAME",
    "GameSession",
    "LoadRefusedError",
    "NoGameError",
    "SaveCorruptError",
    "SaveNotFoundError",
    "SaveUnreadableError",
    "SessionError",
    "UnsupportedSaveVersionError",
]
