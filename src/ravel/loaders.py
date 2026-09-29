import os.path
from pathlib import Path

import attr

from . import exceptions


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
        base = Path(self.base_path).resolve()
        filepath = (base / (name + self.extension)).resolve()
        if not filepath.is_relative_to(base):
            raise exceptions.RulebookNotFound("%s: include escapes the story directory" % name)
        if not filepath.exists():
            raise exceptions.RulebookNotFound(name)

        with filepath.open(encoding="utf-8") as fi:
            source = fi.read()

        is_up_to_date = self.get_up_to_date_checker(filepath)

        return source, is_up_to_date


class MemoryLoader(BaseLoader):
    """Serve rulebooks from an in-memory mapping of name to source text."""

    def __init__(self, sources: dict[str, str]) -> None:
        self.sources = dict(sources)

    def get_source(self, environment, name):
        raise NotImplementedError()
