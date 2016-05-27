from collections import namedtuple
import operator as op

from parsimonious import Grammar

from . import grammars
from .expressions import BaseExpressionParser


BaseComparison = namedtuple('BaseComparison', ['quality', 'comparison', 'expression'])


class Comparison(BaseComparison):
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


class ComparisonParser(BaseExpressionParser):
    grammar = Grammar(
        ("comparison = ws? quality ws comparator ws expression ws?"
         + grammars.base_expression_grammar)
    )

    def visit_comparator(self, node, children):
        return node.text

    def visit_comparison(self, node, children):
        children = self.reduce_children(children)
        return Comparison(*children)
