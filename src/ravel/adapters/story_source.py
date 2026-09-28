"""``FileSystemStorySource``: compiles a ``Story`` from a directory of ``.ravel`` files."""

import os
from pathlib import Path

from ravel.engine.story import Story
from ravel.environments import Environment
from ravel.loaders import FileSystemLoader


class FileSystemStorySource:
    """A ``StorySource`` that compiles ``directory`` fresh on every ``load()`` call."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self._directory = Path(directory)

    def load(self) -> Story:
        """Compile the story rooted at ``directory``; raises ``ravel.exceptions.*`` on bad source."""
        environment = Environment(loader=FileSystemLoader(base_path=self._directory))
        return Story.from_rulebook(environment.load())
