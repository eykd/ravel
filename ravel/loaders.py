import codecs

import attr
from path import Path

from . import exceptions


class BaseLoader:
    def load(self, environment, name):
        source, is_up_to_date = self.get_source(environment, name)
        return environment.compile_rulebook(source, name, is_up_to_date)

    def get_source(self, environment, name):
        raise NotImplementedError()


@attr.s
class FileSystemLoader(BaseLoader):
    base_path = attr.ib(default='.', convert=Path)
    extension = attr.ib(default='.ravel')

    def get_source(self, environment, name):
        filepath = self.base_path / (name + self.extension)
        if not filepath.exists():
            raise exceptions.RulebookNotFound(name)
        mtime = filepath.getmtime()
        with codecs.open(filepath, encoding='utf-8') as fi:
            source = fi.read()

        def is_up_to_date():
            try:
                return mtime == filepath.getmtime()
            except OSError:
                return False

        return source, is_up_to_date
