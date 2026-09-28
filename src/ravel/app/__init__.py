"""The application layer: sessions, ports, and the save format.

Errors are defined in ``ravel.app.saves`` and re-exported here (contracts/session-api.md).
``GameSession`` itself lands in a later leaf (``ravel.app.session``).
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

__all__ = [
    "LoadRefusedError",
    "NoGameError",
    "SaveCorruptError",
    "SaveNotFoundError",
    "SaveUnreadableError",
    "SessionError",
    "UnsupportedSaveVersionError",
]
