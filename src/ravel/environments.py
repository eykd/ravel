from __future__ import annotations

from typing import TYPE_CHECKING

import attr

from ravel import loaders

if TYPE_CHECKING:  # pragma: nocover
    from ravel.loaders import BaseLoader


@attr.s
class Environment:
    loader: BaseLoader = attr.ib(default=attr.Factory(lambda: loaders.FileSystemLoader()))
    initializing_name: str = attr.ib(default="begin")

    def load(self):
        return self.loader.load_rulebook(self, self.initializing_name)
