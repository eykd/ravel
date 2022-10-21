from __future__ import annotations

from collections import OrderedDict, defaultdict, deque
from typing import TYPE_CHECKING, Callable, Union

import attr
import syml
from pyrsistent import freeze

from ravel import loaders
from ravel.compiler import rulebooks

if TYPE_CHECKING:
    from pyrsistent import PMap
    from syml.types import Source

    from ravel.loaders import BaseLoader


@attr.s
class Environment:
    loader: BaseLoader = attr.ib(default=attr.Factory(lambda: loaders.FileSystemLoader()))
    initializing_name: str = attr.ib(default="begin")

    def load(self):
        return self.loader.load_rulebook(self, self.initializing_name)
