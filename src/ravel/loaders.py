import os.path
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import attr

from . import exceptions

MAX_RULEBOOK_BYTES: Final = 1_048_576  # 1 MiB of UTF-8 source per rulebook


def _check_size(name: str, size: int) -> None:
    if size > MAX_RULEBOOK_BYTES:
        raise exceptions.RulebookTooLargeError("%s: rulebook source exceeds %d bytes" % (name, MAX_RULEBOOK_BYTES))


class BaseLoader:
    def load(self, environment, name):
        source, is_up_to_date = self.get_source(environment, name)
        return environment.compile_rulebook(source, name, is_up_to_date)

    def get_source(self, environment, name):
        raise NotImplementedError()


@attr.s
class FileSystemLoader(BaseLoader):
    base_path = attr.ib(default=".")
    extension = attr.ib(default=".ravel")

    def get_up_to_date_checker(self, filepath):
        filepath = Path(filepath)
        try:
            mtime = os.path.getmtime(filepath)
        except OSError:
            mtime = 0.0

        def is_up_to_date():
            try:
                return mtime == os.path.getmtime(filepath)
            except OSError:
                return False

        return is_up_to_date

    def get_source(self, environment, name):
        if "\0" in name:
            raise exceptions.RulebookNotFound("%r: invalid rulebook name" % name)
        base = Path(self.base_path).resolve()
        filepath = (base / (name + self.extension)).resolve()
        if not filepath.is_relative_to(base):
            raise exceptions.RulebookNotFound("%s: include escapes the story directory" % name)
        if not filepath.is_file():
            raise exceptions.RulebookNotFound(name)

        try:
            with filepath.open("rb") as fi:
                data = fi.read(MAX_RULEBOOK_BYTES + 1)
        except OSError:
            raise exceptions.RulebookNotFound(name) from None
        _check_size(name, len(data))
        try:
            source = data.decode("utf-8")
        except UnicodeDecodeError:
            raise exceptions.ParseError("%s: rulebook source is not valid UTF-8" % name) from None

        is_up_to_date = self.get_up_to_date_checker(filepath)

        return source, is_up_to_date


class MemoryLoader(BaseLoader):
    """Serve rulebooks from an in-memory mapping of name to source text."""

    def __init__(self, sources: Mapping[str, str]) -> None:
        self.sources = dict(sources)

    def get_source(self, environment, name) -> tuple[str, Callable[[], bool]]:
        try:
            source = self.sources[name]
        except KeyError:
            raise exceptions.RulebookNotFound(name) from None
        _check_size(name, len(source.encode("utf-8", "surrogatepass")))
        return source, lambda: True
