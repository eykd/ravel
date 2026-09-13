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
        filepath = Path(self.base_path) / (name + self.extension)
        if not filepath.exists():
            raise exceptions.RulebookNotFound(name)

        with filepath.open(encoding="utf-8") as fi:
            source = fi.read()

        is_up_to_date = self.get_up_to_date_checker(filepath)

        return source, is_up_to_date
