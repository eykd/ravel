"""``FileSystemStorySource``: compiles a ``Story`` from a directory of ``.ravel`` files."""

import os
from collections.abc import Mapping
from pathlib import Path

from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader, MemoryLoader


class FileSystemStorySource:
    """A ``StorySource`` that compiles ``directory`` fresh on every ``load()`` call."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self._directory = Path(directory)

    def load(self) -> Story:
        """Compile the story rooted at ``directory``; raises ``ravel.exceptions.*`` on bad source."""
        environment = Environment(loader=FileSystemLoader(base_path=self._directory))
        return Story.from_rulebook(environment.load())


class MemoryStorySource:
    """A ``StorySource`` that compiles a mapping of rulebook name to source text; no filesystem access."""

    def __init__(self, sources: Mapping[str, str], entry: str = "begin") -> None:
        self._sources = dict(sources)
        self._entry = entry

    def load(self) -> Story:
        """Compile the story rooted at ``entry``; raises ``ravel.exceptions.*`` on bad source."""
        environment = Environment(loader=MemoryLoader(self._sources), initializing_name=self._entry)
        return Story.from_rulebook(environment.load())
