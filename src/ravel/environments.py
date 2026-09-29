import re
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
# An inline list marker (``- - - x``) costs syml roughly twice the stack frames of an indentation level, so a
# one-line chain that the depth cap above admits (122-128 markers) overflows the default recursion limit
# (ravel-h6v.34). Markers per line are therefore capped separately. Measured: syml survives ~110 markers at
# indent 0 from a shallow stack and ~80 from a stack 300 frames deep; 64 leaves headroom in both, and 64
# markers plus up to 64 indentation levels (the 128-level total) still load from that deep stack.
MAX_INLINE_LIST_MARKERS: Final = 64

# The authoritative per-rulebook source cap. ``compile_rulebook`` enforces it for every loader, shipped or
# custom; ``FileSystemLoader`` also uses it to bound its read to cap + 1 bytes (an early, memory-safe check).
MAX_RULEBOOK_BYTES: Final = 1_048_576  # 1 MiB of UTF-8 source per rulebook


def check_rulebook_size(name: str, size: int) -> None:
    """Raise ``RulebookTooLargeError`` when ``size`` bytes of source for rulebook ``name`` exceed the cap."""
    if size > MAX_RULEBOOK_BYTES:
        raise exceptions.RulebookTooLargeError(
            "%s: rulebook source exceeds %d bytes" % (exceptions.printable(name), MAX_RULEBOOK_BYTES)
        )


# The scan must see exactly the lines syml lexes, or it drifts from the parser it guards (ravel-h6v.30):
# str.splitlines() also breaks on \x0b \x0c \x1c-\x1e \x85 \u2028 \u2029, and str.lstrip() eats every
# Unicode space, so one such character per label used to reset the scan. It therefore reuses syml's own
# pre-processing (BOM strip, \r\n / \r -> \n, tab-indentation check), blank test, and grammar rules for
# comments (column 0 only) and indentation (spaces only).
_SYML_COMMENT: Final = syml.parsers.SymlParser.grammar["comment"].re
_SYML_INDENT: Final = syml.parsers.SymlParser.grammar["indent"].re
# A line can nest within itself (ravel-h6v.33): after a list marker syml's ``value`` rule tries
# ``structure`` again, so ``- - - x`` is three nested lists and ``- a: b`` puts the key ``a`` one level
# below the marker, at the column where the key starts. Each marker and an inline key count as a level.
_SYML_LIST_MARKER: Final = re.compile(r"-(?:[ \t]+|$)")
_SYML_KEY: Final = re.compile(syml.basetypes.KEY_PATTERN_SOURCE + r":(?:[ \t]+|$)")


def _source_nesting_depth(source: str, filename: str = "") -> int:
    """Return the deepest indentation nesting in ``source`` without parsing it.

    Raises ``syml.exceptions.TabIndentationError`` for a tab in leading whitespace, as syml would.
    """
    stack: list[int] = []
    deepest = 0
    for line in syml.preprocess.preprocess(source, filename=filename or None).normalized.split("\n"):
        if syml.preprocess.is_blank(line) or _SYML_COMMENT.match(line):
            continue
        column = _SYML_INDENT.match(line).end()
        columns = []
        while marker := _SYML_LIST_MARKER.match(line, column):
            columns.append(column)
            column = marker.end()
        if len(columns) > MAX_INLINE_LIST_MARKERS:
            raise exceptions.ParseError(
                "Rulebook %s has %d inline list markers on one line; the maximum supported is %d"
                % (exceptions.bounded_repr(filename or "<rulebook>"), len(columns), MAX_INLINE_LIST_MARKERS)
            )
        if not columns or _SYML_KEY.match(line, column):
            columns.append(column)  # a plain line (key or text) is a level at its indent; an inline key too
        for level in columns:
            while stack and stack[-1] > level:
                stack.pop()
            if not stack or stack[-1] < level:
                stack.append(level)
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
            ruleset["rules"].sort(key=rulebooks.rule_sort_key)

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
        check_rulebook_size(label, len(source.encode("utf-8", "surrogatepass")))
        try:
            depth = _source_nesting_depth(source, name)
            if depth > MAX_SOURCE_NESTING_DEPTH:
                raise exceptions.ParseError(
                    "Rulebook %s nests %d indentation levels deep; the maximum supported is %d"
                    % (exceptions.bounded_repr(label), depth, MAX_SOURCE_NESTING_DEPTH)
                )
            data = syml.parsers.parse(source, filename=name).as_source()
        except RecursionError as error:
            raise exceptions.ParseError(
                "Rulebook %s is nested too deeply to parse" % exceptions.bounded_repr(label)
            ) from error
        except syml.exceptions.ParseError as error:
            raise exceptions.ParseError(str(error)) from error

        prefix = name + self.location_separator if name else ""
        rulebook = rulebooks.compile_rulebook(self, data, prefix)
        rulebook["is_up_to_date"] = is_up_to_date
        return rulebook
