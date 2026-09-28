"""``FileSaveStore``: atomic, clobber-guarded save read/write (contracts/session-api.md)."""

from pathlib import Path


class FileSaveStore:
    """A ``SaveStore`` backed by plain files under ``base`` (or ``Path.cwd()`` if ``None``)."""

    def __init__(self, base: Path | None = None) -> None:
        raise NotImplementedError

    def write(self, name: str, data: bytes) -> str:
        """Atomically write ``data`` to ``name``, guarding against clobbering a foreign file."""
        raise NotImplementedError

    def read(self, name: str) -> bytes:
        """Read at most ``MAX_SAVE_BYTES + 1`` bytes from ``name``; refuses non-regular files."""
        raise NotImplementedError
