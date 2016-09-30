import operator as op

import attr


@attr.s
class Choice:
    choice = attr.ib()


@attr.s
class Comparison:
    quality = attr.ib()
    comparison = attr.ib()
    expression = attr.ib()

    _operators = {
        '>': op.gt,
        '>=': op.ge,
        '==': op.eq,
        '<=': op.le,
        '<': op.lt,
    }

    def get_operator(self):
        return self._operators[self.comparison]

    def get_expression(self, qvalue):
        return self.expression

    def __call__(self, qvalue):
        return self.get_operator()(qvalue, self.get_expression(qvalue))

    def __repr__(self):
        return "(%r %s %r)" % (self.quality, self.comparison, self.expression)


@attr.s
class Constraint:
    kind = attr.ib()
    value = attr.ib()


@attr.s
class Effect:
    operation = attr.ib()


@attr.s
class Expression:
    term1 = attr.ib()
    operator = attr.ib()
    term2 = attr.ib()


@attr.s
class GetChoice:
    pass


@attr.s
class Operation:
    quality = attr.ib()
    operation = attr.ib()
    expression = attr.ib()
    constraint = attr.ib()


@attr.s
class Pos:
    index = attr.ib()
    line = attr.ib()
    column = attr.ib()


@attr.s
class Predicate:
    name = attr.ib()
    predicate = attr.ib()


@attr.s
class Situation:
    intro = attr.ib()
    directives = attr.ib()


@attr.s
class Source:
    start = attr.ib()
    end = attr.ib()
    text = attr.ib()

    def __repr__(self):
        return 'Line %s, Column %s (index %s): %r' % (
            self.start.line, self.start.column, self.start.index, self.text
        )


@attr.s
class Text:
    text = attr.ib()
    sticky = attr.ib(default=False)
    predicate = attr.ib(default=None)

    def __str__(self):
        return self.text


@attr.s
class VALUE:
    pass


@attr.s
class Rule:
    name = attr.ib()
    predicates = attr.ib()
