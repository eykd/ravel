"""The read-only compiled story an engine plays, and its stable content identity."""

import hashlib
import json
from collections.abc import Mapping
from typing import Final, Self

import attrs
from attrs import field, frozen

from ravel import types
from ravel.engine.state import LocationId

IR_VERSION: Final = 1

type Canonical = str | int | float | bool | None | list[Canonical] | dict[str, Canonical]


def _canonical(value: object) -> Canonical:
    """Encode ``value`` as plain JSON data, refusing anything without a stable encoding."""
    if value is types.VALUE:
        return {"type": "VALUE"}
    if isinstance(value, str):
        return str(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, Mapping):
        encoded: dict[str, Canonical] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError("cannot fingerprint a mapping with non-str key %r" % (key,))
            encoded[key] = _canonical(value[key])
        return encoded
    cls = type(value)
    if attrs.has(cls):
        fields: dict[str, Canonical] = {"type": cls.__name__}
        for attribute in attrs.fields(cls):
            fields[attribute.name] = _canonical(getattr(value, attribute.name))
        return fields
    raise TypeError("cannot fingerprint a value of type %s" % cls.__name__)


def _dumps(value: Canonical) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _encode_ruleset(ruleset: types.Ruleset) -> Canonical:
    rules: list[Canonical] = [[_canonical(rule.name), _canonical(rule.predicates)] for rule in ruleset["rules"]]
    rules.sort(key=_dumps)
    return {"rules": rules, "locations": _canonical(ruleset["locations"])}


def fingerprint(rulebook: types.CompiledRulebook) -> str:
    """Return the ``sha256:`` content identity of ``rulebook``.

    ``metadata`` is excluded; everything else is encoded canonically so the identity is stable
    across directories, whitespace and comment edits, and hash seeds.
    """
    payload: Canonical = {
        "ir": IR_VERSION,
        "rulebook": {concept: _encode_ruleset(ruleset) for concept, ruleset in rulebook["rulebook"].items()},
        "givens": _canonical(rulebook["givens"]),
    }
    digest = hashlib.sha256(_dumps(payload).encode("utf-8")).hexdigest()
    return "sha256:%s" % digest


@frozen
class Story:
    """A compiled rulebook plus its identity; shared read-only between games."""

    rulebook: types.CompiledRulebook = field(eq=False)
    identity: str
    end_labels: frozenset[str]

    @classmethod
    def from_rulebook(cls, rulebook: types.CompiledRulebook) -> Self:
        """Wrap ``rulebook``, computing its identity and end labels."""
        # No directive can end a story yet, so there are no end labels to collect.
        return cls(rulebook=rulebook, identity=fingerprint(rulebook), end_labels=frozenset())

    def _locations(self) -> Mapping[str, object]:
        ruleset = self.rulebook["rulebook"].get("Situation")
        return {} if ruleset is None else ruleset["locations"]

    def situation(self, location: LocationId) -> types.Situation:
        """Return the situation at ``location``; ``KeyError`` if there is none."""
        found = self._locations().get(location)
        if not isinstance(found, types.Situation):
            raise KeyError(location)
        return found

    def has_location(self, location: LocationId) -> bool:
        """Return whether ``location`` names a situation."""
        return isinstance(self._locations().get(location), types.Situation)

    @property
    def givens(self) -> tuple[types.Operation, ...]:
        """Return the story's initial quality operations, in order."""
        return tuple(self.rulebook["givens"])
