from collections import namedtuple

from .parsers import BaseParser


Expression = namedtuple('Expression', ['term1', 'operator', 'term2'])


class VALUE: pass


class BaseExpressionParser(BaseParser):
    visit_setter = BaseParser.get_text
    visit_simple_quality = BaseParser.get_text

    def visit_quoted_quality(self, node, children):
        return node.text[1:-1]

    def visit_float(self, node, children):
        return float(node.text)

    def visit_integer(self, node, children):
        return int(node.text)

    def visit_string(self, node, children):
        return node.children[0].children[1].text

    def visit_qvalue(self, node, children):
        return VALUE

    def visit_expression(self, node, children):
        expr = children[0]
        if isinstance(expr, list):
            return Expression(*expr)
        else:
            return expr

    visit_multiplicative = visit_divisive = visit_additive = visit_expression

    visit_add = visit_subtract = BaseParser.get_text
    visit_multiply = BaseParser.get_text
    visit_floor_div = visit_divide = visit_modulus = BaseParser.get_text
