from __future__ import annotations
from typing import Any, TYPE_CHECKING
from collections.abc import Sequence
from parsimonious import Grammar, NodeVisitor
from pyrsistent import pmap, pvector

from ravel import grammars, types

if TYPE_CHECKING:
    from parsimonious.nodes import Node
    from pyrsistent import PVector
    from ravel.types import SourceStr


class BaseParser(NodeVisitor):
    def reduce_children(self, children: Sequence) -> Any:
        children = [c for c in children if c is not None]
        if children:
            return children if len(children) > 1 else children[0]
        else:
            return None

    def get_text(self, node: Node, children: Sequence) -> SourceStr:
        return node.text

    def generic_visit(self, node: Node, children) -> Any:
        return self.reduce_children(children)


class BaseExpressionParser(BaseParser):
    visit_setter = BaseParser.get_text
    visit_simple_quality = BaseParser.get_text

    def visit_quoted_quality(self, node: Node, children: Sequence) -> SourceStr:
        return node.text[1:-1]

    def visit_bracketed_quality(self, node: Node, children: Sequence) -> SourceStr:
        return node.text[1:-1]

    def visit_float(self, node: Node, children: Sequence) -> float:
        return float(node.text)

    def visit_integer(self, node: Node, children: Sequence) -> int:
        return int(node.text)

    def visit_string(self, node: Node, children: Sequence) -> SourceStr:
        return node.children[0].children[1].text

    def visit_qvalue(self, node: Node, children: Sequence) -> types.VALUE:
        return types.VALUE

    def visit_expression(self, node: Node, children: Sequence) -> types.Expression:
        expr = children[0]
        if isinstance(expr, list):
            return types.Expression(*expr)
        else:
            return expr

    visit_multiplicative = visit_divisive = visit_additive = visit_expression

    visit_add = visit_subtract = BaseParser.get_text
    visit_multiply = BaseParser.get_text
    visit_floor_div = visit_divide = visit_modulus = BaseParser.get_text


class ComparisonParser(BaseExpressionParser):
    grammar = Grammar(("comparison = ws? quality ws comparator ws expression ws?" + grammars.base_expression_grammar))

    def visit_comparator(self, node: Node, children: Sequence) -> SourceStr:
        return node.text

    def visit_comparison(self, node: Node, children: Sequence) -> types.Comparison:
        children = self.reduce_children(children)
        return types.Comparison(*children)


class IntroTextParser(BaseParser):
    grammar = Grammar(grammars.intro_text_grammar)

    def visit_head(self, node: Node, children: Sequence) -> SourceStr:
        return node.text

    def visit_suffix(self, node: Node, children: Sequence) -> SourceStr:
        return node.text.strip("[]")

    def visit_tail(self, node: Node, children: Sequence) -> SourceStr:
        return node.text

    def visit_intro(self, node: Node, children: Sequence) -> PVector:
        head, rest = children
        if rest is not None:
            suffix, tail = rest
        else:
            suffix = tail = ""

        return pvector(
            [
                types.Text(head + suffix),
                types.Text(head + tail),
            ]
        )


class PlainTextParser(ComparisonParser):
    grammar = Grammar(grammars.plain_text_grammar)

    def visit_text(self, node: Node, children: Sequence) -> SourceStr:
        return node.text

    def visit_glue(self, node: Node, children: Sequence) -> bool:
        return True

    def visit_line(self, node: Node, children: Sequence) -> types.Text:
        predicate, text, *sticky = children
        sticky = self.reduce_children(sticky)
        return types.Text(text, sticky=bool(sticky), predicate=predicate)

    def visit_comparison(self, node: Node, children: Sequence) -> types.Predicate:
        comparison = super().visit_comparison(node, children)
        return types.Predicate(comparison.quality, comparison)


class OperationParser(BaseExpressionParser):
    grammar = Grammar(grammars.operation_grammar)

    def visit_constraint(self, node: Node, children: Sequence) -> types.Constraint:
        return types.Constraint(node.children[0].text, self.reduce_children(children))

    def visit_operation(self, node: Node, children: Sequence) -> types.Operation:
        children = self.reduce_children(children)
        quality, operator, expr = children
        if isinstance(expr, list):
            expr, constraint = expr
        else:
            constraint = None
        return types.Operation(quality, operator, expr, constraint)
