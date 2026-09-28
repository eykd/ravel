"""``FileSaveStore``: atomic, clobber-guarded save read/write (contracts/session-api.md)."""

import os
import stat
import tempfile
from pathlib import Path

from ravel.app.saves import MAX_SAVE_BYTES, SAVE_MAGIC


class FileSaveStore:
    """A ``SaveStore`` backed by plain files under ``base`` (or ``Path.cwd()`` if ``None``)."""

    def __init__(self, base: Path | None = None) -> None:
        self._base = base

    def _path(self, name: str) -> Path:
        base = self._base if self._base is not None else Path.cwd()
        return base / name

    def write(self, name: str, data: bytes) -> str:
        """Atomically write ``data`` to ``name``, guarding against clobbering a foreign file."""
        target = self._path(name)
        if target.exists() and target.stat().st_size > 0:
            with open(target, "rb") as existing:
                prefix = existing.read(len(SAVE_MAGIC))
            if prefix != SAVE_MAGIC:
                raise FileExistsError("%s exists and is not a ravel save" % target)

        fd, tmp_name = tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as tmp_file:
                tmp_file.write(data)
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(tmp_name, 0o666 & ~mask)
            os.replace(tmp_name, target)
        except BaseException:
            os.unlink(tmp_name)
            raise
        return str(target)

    def read(self, name: str) -> bytes:
        """Read at most ``MAX_SAVE_BYTES + 1`` bytes from ``name``; refuses non-regular files."""
        target = self._path(name)
        file_stat = os.stat(target)
        if not stat.S_ISREG(file_stat.st_mode):
            raise OSError("not a regular file: %s" % target)
        with open(target, "rb") as save_file:
            return save_file.read(MAX_SAVE_BYTES + 1)
