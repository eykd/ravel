import operator as op

import attr
from syml.types import Pos, Source  # noqa

from ravel.utils.data import evaluate_term


@attr.s(slots=True)
class Choice:
    choice = attr.ib()


@attr.s(slots=True, repr=False)
class Comparison:
    quality = attr.ib()
    comparator = attr.ib()
    expression = attr.ib()

    _comparators = {
        ">": op.gt,
        ">=": op.ge,
        "==": op.eq,
        "=": op.eq,
        "<=": op.le,
        "<": op.lt,
        "!=": op.ne,
    }

    def get_comparators(self):
        return self._comparators[self.comparator]

    def get_expression(self, **kwargs):
        return evaluate_term(self.expression, **kwargs)

    def evaluate(self, qvalue, **kwargs):
        if qvalue is None:
            qvalue = 0
        return self.get_comparators()(
            qvalue, self.get_expression(qvalue=qvalue, **kwargs)
        )

    def check(self, qualities, **kwargs):
        value = qualities.get(self.quality)
        return self.evaluate(value, **kwargs)

    def __call__(self, qvalue, **kwargs):
        return self.evaluate(qvalue, **kwargs)

    def __repr__(self):
        return "(%r %s %r)" % (self.quality, self.comparator, self.expression)


@attr.s(slots=True)
class Constraint:
    kind = attr.ib()
    value = attr.ib()


@attr.s(slots=True)
class Effect:
    operation = attr.ib()


@attr.s(slots=True)
class Expression:
    term1 = attr.ib()
    operator = attr.ib()
    term2 = attr.ib()

    _operators = {
        "+": op.add,
        "-": op.sub,
        "*": op.mul,
        "//": op.floordiv,
        "/": op.truediv,
        "%": op.mod,
    }

    def get_operator(self):
        return self._operators[self.operator]

    def evaluate(self, **kwargs):
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
    quality = attr.ib()
    operator = attr.ib()
    expression = attr.ib()
    constraint = attr.ib(default=None)

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


@attr.s(slots=True)
class Predicate:
    name = attr.ib()
    predicate = attr.ib()

    def check(self, qualities, **kwargs):
        if self.predicate is None:
            return True

        return self.predicate.check(qualities, **kwargs)


@attr.s(slots=True)
class Situation:
    intro = attr.ib()
    directives = attr.ib()


@attr.s(slots=True)
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


@attr.s(slots=True)
class VALUE:
    pass


@attr.s(slots=True)
class Rule:
    name = attr.ib()
    predicates = attr.ib()
