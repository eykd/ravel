import codecs

from path import Path

from . import exceptions


class BaseLoader:
    def load(self, environment, name):
        source, filepath, is_up_to_date = self.get_source(environment, name)
        return environment.compile_rulebook(source, filepath, is_up_to_date)

    def get_source(self, environment, name):
        raise NotImplementedError()


class FileSystemLoader(BaseLoader):
    def __init__(self, base_path):
        self.base_path = Path(base_path).abspath()

    def get_source(self, environment, name):
        filepath = self.base_path / name
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

        return source, filepath, is_up_to_date
