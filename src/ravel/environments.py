from collections import OrderedDict, defaultdict, deque
from typing import Any, Final

import attr
import syml

from ravel import exceptions
from ravel.compiler import rulebooks

# syml builds its node tree recursively, one Python frame group per indentation level, so a rulebook
# indented a few hundred levels deep raises an untyped RecursionError before the compiler runs (about
# 225 nested ``choice:`` blocks overflow in practice). The source is therefore scanned first and refused
# past this many nested indentation levels. Real stories nest a handful of levels (examples/cloak: 4).
# The compiler's own MAX_CHOICE_NESTING_DEPTH (200) is deliberately higher: it guards rulebook data that
# did not come through this text path.
MAX_SOURCE_NESTING_DEPTH: Final = 128


def _source_nesting_depth(source: str) -> int:
    """Return the deepest indentation nesting in ``source`` without parsing it."""
    stack: list[int] = []
    deepest = 0
    for line in source.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        while stack and stack[-1] > indent:
            stack.pop()
        if not stack or stack[-1] < indent:
            stack.append(indent)
        deepest = max(deepest, len(stack))
    return deepest


def _has_load(instance: object, attribute: object, value: object) -> None:
    if not callable(getattr(value, "load", None)):
        raise TypeError("Environment loader must have a callable load(); got %s" % type(value).__name__)


@attr.s
class Environment:
    loader: Any = attr.ib(validator=_has_load)
    location_separator = attr.ib(default="::")
    initializing_name = attr.ib(default="begin")

    cache: dict[str, Any] = attr.ib(default=attr.Factory(dict))

    def load(self):
        return self.load_rulebook(self.initializing_name)

    def load_rulebook(self, name):
        loaded_rulebooks = OrderedDict()
        names_to_load = deque([name])
        metadata = {}
        givens = []

        while names_to_load:
            name = names_to_load.popleft()
            if name not in loaded_rulebooks:
                rulebook = loaded_rulebooks[name] = self.get_rulebook(name)
                names_to_load.extend(
                    [include_name for include_name in rulebook["includes"] if include_name not in loaded_rulebooks]
                )
                metadata.update(rulebook["metadata"])
                givens.extend(rulebook["givens"])

        master_rulebook = defaultdict(lambda: {"rules": [], "locations": {}})
        for rulebook in loaded_rulebooks.values():
            for concept, ruleset in rulebook["rulebook"].items():
                master_concept = master_rulebook[concept]
                master_concept["rules"].extend(ruleset["rules"])
                master_concept["locations"].update(ruleset["locations"])

        for ruleset in master_rulebook.values():
            ruleset["rules"].sort()

        return {
            "metadata": metadata,
            "rulebook": dict(master_rulebook),
            "givens": givens,
        }

    def get_rulebook(self, name):
        rulebook = self.cache.get(name)
        if rulebook is None or not rulebook["is_up_to_date"]():
            rulebook = self.loader.load(self, name)
            self.cache[name] = rulebook
        return rulebook

    @staticmethod
    def default_is_up_to_date():
        return True

    def compile_rulebook(self, source, name="", is_up_to_date=default_is_up_to_date):
        label = name or "<rulebook>"
        depth = _source_nesting_depth(source)
        if depth > MAX_SOURCE_NESTING_DEPTH:
            raise exceptions.ParseError(
                "Rulebook %r nests %d indentation levels deep; the maximum supported is %d"
                % (label, depth, MAX_SOURCE_NESTING_DEPTH)
            )
        try:
            data = syml.parsers.parse(source, filename=name).as_source()
        except RecursionError as error:
            raise exceptions.ParseError("Rulebook %r is nested too deeply to parse" % label) from error
        except syml.exceptions.ParseError as error:
            raise exceptions.ParseError(str(error)) from error

        prefix = name + self.location_separator if name else ""
        rulebook = rulebooks.compile_rulebook(self, data, prefix)
        rulebook["is_up_to_date"] = is_up_to_date
        return rulebook
