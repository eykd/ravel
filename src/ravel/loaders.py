import os.path
from collections.abc import Callable, Mapping
from pathlib import Path

import attr

from . import exceptions
from .environments import MAX_RULEBOOK_BYTES, check_rulebook_size


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
            raise exceptions.RulebookNotFound("%s: invalid rulebook name" % exceptions.bounded_repr(name))
        base = Path(self.base_path).resolve()
        filepath = (base / (name + self.extension)).resolve()
        if not filepath.is_relative_to(base):
            raise exceptions.RulebookNotFound("%s: include escapes the story directory" % exceptions.printable(name))
        if not filepath.is_file():
            raise exceptions.RulebookNotFound(exceptions.printable(name))

        try:
            with filepath.open("rb") as fi:
                data = fi.read(MAX_RULEBOOK_BYTES + 1)
        except OSError:
            raise exceptions.RulebookNotFound(exceptions.printable(name)) from None
        check_rulebook_size(name, len(data))
        try:
            source = data.decode("utf-8")
        except UnicodeDecodeError:
            raise exceptions.ParseError("%s: rulebook source is not valid UTF-8" % exceptions.printable(name)) from None

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
            raise exceptions.RulebookNotFound(exceptions.printable(name)) from None
        return source, lambda: True
