import operator as op

import attr


@attr.s(slots=True)
class Choice:
    choice = attr.ib()


@attr.s(slots=True)
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


@attr.s(slots=True)
class GetChoice:
    pass


@attr.s(slots=True)
class Operation:
    quality = attr.ib()
    operation = attr.ib()
    expression = attr.ib()
    constraint = attr.ib()


@attr.s(slots=True)
class Pos:
    index = attr.ib()
    line = attr.ib()
    column = attr.ib()


@attr.s(slots=True)
class Predicate:
    name = attr.ib()
    predicate = attr.ib()


@attr.s(slots=True)
class Situation:
    intro = attr.ib()
    directives = attr.ib()


@attr.s(slots=True)
class Source:
    filename = attr.ib()
    start = attr.ib()
    end = attr.ib()
    text = attr.ib()

    def __repr__(self):
        return '%sLine %s, Column %s (index %s): %r' % (
            '%s, ' % self.filename if self.filename else '',
            self.start.line, self.start.column, self.start.index, self.text
        )


@attr.s(slots=True)
class Text:
    text = attr.ib()
    sticky = attr.ib(default=False)
    predicate = attr.ib(default=None)

    def __str__(self):
        return self.text


@attr.s(slots=True)
class VALUE:
    pass


@attr.s(slots=True)
class Rule:
    name = attr.ib()
    predicates = attr.ib()
