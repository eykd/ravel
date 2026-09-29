import operator as op
from collections.abc import Callable
from typing import Any, TypedDict

import attr
from syml.basetypes import Pos, Source  # noqa

from ravel.utils.data import evaluate_term


@attr.s(slots=True)
class Choice:
    choice: Any = attr.ib()


@attr.s(slots=True)
class End:
    outcome: str = attr.ib()


@attr.s(slots=True, repr=False)
class Comparison:
    quality: Any = attr.ib()
    comparator: Any = attr.ib()
    expression: Any = attr.ib()

    _comparators = {
        ">": op.gt,
        ">=": op.ge,
        "==": op.eq,
        "=": op.eq,
        "<=": op.le,
        "<": op.lt,
        "!=": op.ne,
    }

    def get_comparators(self) -> Callable[[Any, Any], Any]:
        return self._comparators[self.comparator]

    def get_expression(self, **kwargs: Any) -> Any:
        return evaluate_term(self.expression, **kwargs)

    def evaluate(self, qvalue: Any, **kwargs: Any) -> Any:
        if qvalue is None:
            qvalue = 0
        return self.get_comparators()(qvalue, self.get_expression(qvalue=qvalue, **kwargs))

    def check(self, qualities: Any, **kwargs: Any) -> Any:
        value = qualities.get(self.quality)
        return self.evaluate(value, **kwargs)

    def __call__(self, qvalue: Any, **kwargs: Any) -> Any:
        return self.evaluate(qvalue, **kwargs)

    def __repr__(self) -> str:
        return "(%r %s %r)" % (self.quality, self.comparator, self.expression)


@attr.s(slots=True)
class Constraint:
    kind: Any = attr.ib()
    value: Any = attr.ib()


@attr.s(slots=True)
class Effect:
    operation: Any = attr.ib()


@attr.s(slots=True)
class Expression:
    term1: Any = attr.ib()
    operator: Any = attr.ib()
    term2: Any = attr.ib()

    _operators = {
        "+": op.add,
        "-": op.sub,
        "*": op.mul,
        "//": op.floordiv,
        "/": op.truediv,
        "%": op.mod,
    }

    def get_operator(self) -> Callable[[Any, Any], Any]:
        return self._operators[self.operator]

    def evaluate(self, **kwargs: Any) -> Any:
        return self.get_operator()(
            evaluate_term(self.term1, **kwargs),
            evaluate_term(self.term2, **kwargs),
        )


@attr.s(slots=True)
class BeginChoices:
    pass


@attr.s(slots=True)
class GetChoice:
    pass


@attr.s(slots=True)
class Operation:
    quality: Any = attr.ib()
    operator: Any = attr.ib()
    expression: Any = attr.ib()
    constraint: Any = attr.ib(default=None)

    _operators = {
        "=": lambda a, b: b,
        "+=": op.add,
        "-=": op.sub,
        "*=": op.mul,
        "//=": op.floordiv,
        "/=": op.truediv,
        "%=": op.mod,
    }

    def get_operator(self) -> Callable[[Any, Any], Any]:
        return self._operators[self.operator]

    def get_expression(self, **kwargs: Any) -> None:
        return

    def evaluate(self, initial_value: Any, **kwargs: Any) -> Any:
        if initial_value is None:
            initial_value = 0
        result = self.get_operator()(
            initial_value,
            evaluate_term(self.expression, **kwargs),
        )
        return result


@attr.s(slots=True)
class Predicate:
    name: Any = attr.ib()
    predicate: Any = attr.ib()

    def check(self, qualities: Any, **kwargs: Any) -> Any:
        if self.predicate is None:
            return True

        return self.predicate.check(qualities, **kwargs)


@attr.s(slots=True)
class Situation:
    intro: Any = attr.ib()
    directives: Any = attr.ib()


@attr.s(slots=True)
class Text:
    text: Any = attr.ib()
    sticky: Any = attr.ib(default=False, repr=False)
    predicate: Any = attr.ib(default=None, repr=False)

    def check(self, qualities: Any, **kwargs: Any) -> Any:
        if self.predicate is None:
            return True

        return self.predicate.check(qualities, **kwargs)

    def __str__(self) -> str:
        return str(self.text)


@attr.s(slots=True)
class VALUE:
    pass


@attr.s(slots=True)
class Value:
    """The ``VALUE`` placeholder: evaluates to the current quality value."""

    def evaluate(self, **kwargs: Any) -> Any:
        raise NotImplementedError


@attr.s(slots=True)
class QualityRef:
    """A reference to a quality by name, evaluated against the current qualities."""

    name: str = attr.ib()

    def evaluate(self, **kwargs: Any) -> Any:
        raise NotImplementedError


@attr.s(slots=True)
class Rule:
    name: Any = attr.ib()
    predicates: Any = attr.ib()


class Ruleset(TypedDict):
    """One concept's compiled rules and the baggage each rule name locates."""

    rules: list[Rule]
    locations: dict[str, object]


class CompiledRulebook(TypedDict):
    """The merged rulebook ``Environment.load()`` returns."""

    metadata: dict[str, str]
    rulebook: dict[str, Ruleset]
    givens: list[Operation]
