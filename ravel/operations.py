from collections import namedtuple

from parsimonious import Grammar

from . import grammars
from .expressions import BaseExpressionParser


Constraint = namedtuple('Constraint', ['kind', 'value'])
Operation = namedtuple('Operation', ['quality', 'operation', 'expression', 'constraint'])


class OperationParser(BaseExpressionParser):
    grammar = Grammar(grammars.operation_grammar)

    def visit_constraint(self, node, children):
        return Constraint(node.children[0].text, self.reduce_children(children))

    def visit_operation(self, node, children):
        children = self.reduce_children(children)
        quality, operator, expr = children
        if isinstance(expr, list):
            expr, constraint = expr
        else:
            constraint = None
        return Operation(quality, operator, expr, constraint)
