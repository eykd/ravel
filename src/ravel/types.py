from __future__ import annotations

import operator as op
from typing import Optional, Union

import attr
from attrs import define, field
from pyrsistent import PMap, PVector
from pyrsistent import pmap, pvector
from syml.types import Pos, Source  # noqa

from ravel.utils.data import evaluate_term

SourceStr = Union[Source, str]


@define(slots=True, frozen=True)
class Rulebook:
    metadata: PMap
    concepts: PMap[str, Concept]
    givens: PVector


@define(slots=True, frozen=True)
class Concept:
    rules: PVector = field(factory=pvector)
    locations: PMap = field(factory=pmap)


@define(slots=True, frozen=True)
class Choice:
    choice: str = field()


@define(slots=True, repr=False, frozen=True)
class Comparison:
    quality: str = field()
    comparator: str = field()
    expression: str = field()

    _comparators = pmap(
        {
            ">": op.gt,
            ">=": op.ge,
            "==": op.eq,
            "=": op.eq,
            "<=": op.le,
            "<": op.lt,
            "!=": op.ne,
        }
    )

    def get_comparators(self):
        return self._comparators[self.comparator]

    def get_expression(self, **kwargs):
        return evaluate_term(self.expression, **kwargs)

    def evaluate(self, qvalue, **kwargs):
        if qvalue is None:
            qvalue = 0
        return self.get_comparators()(qvalue, self.get_expression(qvalue=qvalue, **kwargs))

    def check(self, qualities, **kwargs):
        value = qualities.get(self.quality)
        return self.evaluate(value, **kwargs)

    def __call__(self, qvalue, **kwargs):
        return self.evaluate(qvalue, **kwargs)

    def __repr__(self):
        return "(%r %s %r)" % (self.quality, self.comparator, self.expression)


@define(slots=True, frozen=True)
class Constraint:
    kind: str = field()
    value: str = field()


@define(slots=True, frozen=True)
class Effect:
    operation: Operation = field()


@define(slots=True, frozen=True)
class Expression:
    term1: str = field()
    operator: str = field()
    term2: str = field()

    _operators = pmap(
        {
            "+": op.add,
            "-": op.sub,
            "*": op.mul,
            "//": op.floordiv,
            "/": op.truediv,
            "%": op.mod,
        }
    )

    def get_operator(self):
        return self._operators[self.operator]

    def evaluate(self, **kwargs):
        return self.get_operator()(
            evaluate_term(self.term1, **kwargs),
            evaluate_term(self.term2, **kwargs),
        )


@define(slots=True, frozen=True)
class BeginChoices:
    pass


@define(slots=True, frozen=True)
class GetChoice:
    pass


@define(slots=True, frozen=True)
class Operation:
    quality: str = field()
    operator: str = field()
    expression: str = field()
    constraint: Optional[Constraint] = field(default=None)

    _operators = {
        "=": lambda a, b: b,
        "+=": op.add,
        "-=": op.sub,
        "*=": op.mul,
        "//=": op.floordiv,
        "/=": op.truediv,
        "%=": op.mod,
    }

    def get_operator(self):
        return self._operators[self.operator]

    def get_expression(self, **kwargs):
        return

    def evaluate(self, initial_value, **kwargs):
        if initial_value is None:
            initial_value = 0
        result = self.get_operator()(
            initial_value,
            evaluate_term(self.expression, **kwargs),
        )
        return result


@define(slots=True, frozen=True, order=True)
class Predicate:
    name: str = field()
    comparison: Comparison = field()

    def check(self, qualities, **kwargs):
        if self.comparison is None:
            return True

        return self.comparison.check(qualities, **kwargs)


@define(slots=True, frozen=True)
class Situation:
    intro = field()
    directives = field()


@define(slots=True, frozen=True)
class Text:
    text = field()
    sticky = field(default=False, repr=False)
    predicate = field(default=None, repr=False)

    def check(self, qualities, **kwargs):
        if self.predicate is None:
            return True

        return self.predicate.check(qualities, **kwargs)

    def __str__(self):
        return self.text


@define(slots=True, frozen=True)
class VALUE:
    pass


@define(slots=True, frozen=True, order=True)
class Rule:
    name = field()
    predicates = field()
