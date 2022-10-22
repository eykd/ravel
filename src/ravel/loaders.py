from __future__ import annotations

import codecs
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Callable, Tuple, Union, Dict

import syml
from attrs import define, field, Factory
from path import Path
from pyrsistent import PMap, freeze

from ravel import exceptions
from ravel.compiler import rulebooks
from ravel.types import Concept, Rulebook

if TYPE_CHECKING:
    from syml.types import Source

    from ravel.environments import Environment


@define
class BaseLoader:
    location_separator: str = field(default="::")

    def load(self, environment: Environment, name: str) -> PMap:
        source, is_up_to_date = self.get_source(environment, name)
        return self.compile_rulebook(environment, source, name, is_up_to_date)

    def get_source(self, environment: Environment, name: str):
        raise NotImplementedError()

    @staticmethod
    def default_is_up_to_date() -> bool:
        return True

    def load_rulebook(self, environment: Environment, name: str):
        loaded_rulebooks = {}
        names_to_load = deque([name])
        metadata = {}
        givens = []

        while names_to_load:
            name = names_to_load.popleft()
            if name not in loaded_rulebooks:
                rulebook = loaded_rulebooks[name] = self.get_rulebook(environment, name)
                names_to_load.extend(
                    [include_name for include_name in rulebook["includes"] if include_name not in loaded_rulebooks]
                )
                metadata.update(rulebook["metadata"])
                givens.extend(rulebook["givens"])

        return rulebooks.compile_master_rulebook(loaded_rulebooks.values(), metadata, givens)

    def get_rulebook(self, environment: Environment, name: str) -> PMap:
        rulebook = self.cache.get(name)
        if rulebook is None or not rulebook["is_up_to_date"]():
            rulebook = self.load(environment, name)
            self.cache[name] = rulebook
        return rulebook

    def compile_rulebook(
        self,
        environment: Environment,
        source: Union[str, Source],
        name: str = "",
        is_up_to_date: Callable = default_is_up_to_date,
    ) -> PMap:
        data = syml.loads(source, filename=name)

        prefix = name + self.location_separator if name else ""
        rulebook = rulebooks.compile_rulebook(environment, data, prefix)
        return rulebook.set("is_up_to_date", is_up_to_date)


@define
class FileSystemLoader(BaseLoader):
    base_path: str = field(default=".")
    extension: str = field(default=".ravel")
    cache = field(default=Factory(dict))

    def get_up_to_date_checker(self, filepath: Union[str, Path]) -> Callable:
        filepath = Path(filepath)
        try:
            mtime = filepath.getmtime()
        except OSError:
            mtime = 0.0

        def is_up_to_date():
            try:
                print("was %s, now %s" % (mtime, filepath.getmtime()))
                return mtime == filepath.getmtime()
            except OSError:
                return False

        return is_up_to_date

    def get_source(self, environment: Environment, name: str) -> Tuple[str, Callable]:
        filepath = Path(self.base_path) / (name + self.extension)
        if not filepath.exists():
            raise exceptions.RulebookNotFound(name)

        with codecs.open(filepath, encoding="utf-8") as fi:
            source = fi.read()

        is_up_to_date = self.get_up_to_date_checker(filepath)

        return source, is_up_to_date
