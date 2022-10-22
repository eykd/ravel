from __future__ import annotations
import operator as op
from typing import Union, Optional

import attr
from pyrsistent import pmap
from syml.types import Pos, Source  # noqa

from ravel.utils.data import evaluate_term


SourceStr = Union[Source, str]


@attr.s(slots=True, frozen=True)
class Choice:
    choice: str = attr.ib()


@attr.s(slots=True, repr=False, frozen=True)
class Comparison:
    quality: str = attr.ib()
    comparator: str = attr.ib()
    expression: str = attr.ib()

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


@attr.s(slots=True, frozen=True)
class Constraint:
    kind: str = attr.ib()
    value: str = attr.ib()


@attr.s(slots=True, frozen=True)
class Effect:
    operation: Operation = attr.ib()


@attr.s(slots=True, frozen=True)
class Expression:
    term1: str = attr.ib()
    operator: str = attr.ib()
    term2: str = attr.ib()

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


@attr.s(slots=True, frozen=True)
class BeginChoices:
    pass


@attr.s(slots=True, frozen=True)
class GetChoice:
    pass


@attr.s(slots=True, frozen=True)
class Operation:
    quality: str = attr.ib()
    operator: str = attr.ib()
    expression: str = attr.ib()
    constraint: Optional[Constraint] = attr.ib(default=None)

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


@attr.s(slots=True, frozen=True)
class Predicate:
    name: str = attr.ib()
    comparison: Comparison = attr.ib()

    def check(self, qualities, **kwargs):
        if self.comparison is None:
            return True

        return self.comparison.check(qualities, **kwargs)


@attr.s(slots=True, frozen=True)
class Situation:
    intro = attr.ib()
    directives = attr.ib()


@attr.s(slots=True, frozen=True)
class Text:
    text = attr.ib()
    sticky = attr.ib(default=False, repr=False)
    predicate = attr.ib(default=None, repr=False)

    def check(self, qualities, **kwargs):
        if self.predicate is None:
            return True

        return self.predicate.check(qualities, **kwargs)

    def __str__(self):
        return self.text


@attr.s(slots=True, frozen=True)
class VALUE:
    pass


@attr.s(slots=True, frozen=True)
class Rule:
    name = attr.ib()
    predicates = attr.ib()
