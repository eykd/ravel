from collections import namedtuple
import re
import textwrap

from parsimonious import NodeVisitor, Grammar

from .types import Comparison, Constraint, Expression, Operation, VALUE


float_cp = re.compile(r'^\d*\.\d+$')


base_grammar = textwrap.dedent(r"""
    quality               = quoted_quality / simple_quality
    quoted_quality        = ~'"[^"]+"'
    simple_quality        = ~'[^\s]+'

    expression            = additive
    additive              = (multiplicative ws? (add / subtract) ws? additive)
                            / multiplicative
    multiplicative        = (divisive ws? multiply ws? multiplicative)
                            / divisive
    divisive              = (primary ws? (floor_div / divide / modulus) ws? divisive)
                            / primary
    primary               = value / (open_paren ws? additive ws? close_paren)


    open_paren            = "("
    close_paren           = ")"

    add                   = "+"
    subtract              = "-"
    multiply              = "*"
    floor_div             = "//"
    divide                = "/"
    modulus               = "%"

    setter                = set_add / set_subtract / set_multiply / set_floor_div / set_divide / set_modulus / set
    set                   = "="
    set_add               = add set
    set_subtract          = subtract set
    set_multiply          = multiply set
    set_floor_div         = floor_div set
    set_divide            = divide set
    set_modulus           = modulus set

    constraint            = (max / min) ws number
    max                   = "max"
    min                   = "min"

    comparator            = gte / gt / lte / lt / ne / eq
    gte                   = ">="
    gt                    = ">"
    lte                   = "<="
    lt                    = "<"
    ne                    = "!="
    eq                    = "=="

    ws                    = ~"\s+"
    end                   = ~"\s*$"

    value                 = number / string / qvalue

    qvalue                = "value"

    number                = float / integer
    float                 = ~"\d+\.\d*"
    integer               = ~"\d+"

    string                = ('""" + '"""' + r"""' ~'([^"])+' '""" + '"""' + r"""')
                            / ("'''" ~"([^'])+" "'''")
                            / ("```" ~"([^`])+" "```")
                            / ('"' ~'([^"])+' '"')
                            / ("'" ~"([^'])+" "'")
                            / ("`" ~"([^`])+" "`")
""")


class _BaseParser(NodeVisitor):
    def reduce_children(self, children):
        children = [c for c in children if c is not None]
        if children:
            return children if len(children) > 1 else children[0]
        else:
            return None

    def get_text(self, node, children):
        return node.text

    def generic_visit(self, node, children):
        return self.reduce_children(children)

    visit_setter = get_text
    visit_simple_quality = get_text

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

    visit_add = visit_subtract = get_text
    visit_multiply = get_text
    visit_floor_div = visit_divide = visit_modulus = get_text


class OperationParser(_BaseParser):
    grammar = Grammar(
        ("operation = ws? quality ws setter ws (expression (ws constraint)?) ws?"
         + base_grammar)
    )

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


class ComparisonParser(_BaseParser):
    grammar = Grammar(
        ("comparison = ws? quality ws comparator ws expression ws?"
         + base_grammar)
    )

    def visit_comparator(self, node, children):
        return node.text

    def visit_comparison(self, node, children):
        children = self.reduce_children(children)
        return Comparison(*children)
