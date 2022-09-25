from parsimonious import Grammar, NodeVisitor

from ravel import grammars, types


class BaseParser(NodeVisitor):
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


class BaseExpressionParser(BaseParser):
    visit_setter = BaseParser.get_text
    visit_simple_quality = BaseParser.get_text

    def visit_quoted_quality(self, node, children):
        return node.text[1:-1]

    def visit_bracketed_quality(self, node, children):
        return node.text[1:-1]

    def visit_float(self, node, children):
        return float(node.text)

    def visit_integer(self, node, children):
        return int(node.text)

    def visit_string(self, node, children):
        return node.children[0].children[1].text

    def visit_qvalue(self, node, children):
        return types.VALUE

    def visit_expression(self, node, children):
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
    grammar = Grammar(
        (
            "comparison = ws? quality ws comparator ws expression ws?"
            + grammars.base_expression_grammar
        )
    )

    def visit_comparator(self, node, children):
        return node.text

    def visit_comparison(self, node, children):
        children = self.reduce_children(children)
        return types.Comparison(*children)


class IntroTextParser(BaseParser):
    grammar = Grammar(grammars.intro_text_grammar)

    def visit_head(self, node, children):
        return node.text

    def visit_suffix(self, node, children):
        return node.text.strip("[]")

    def visit_tail(self, node, children):
        return node.text

    def visit_intro(self, node, children):
        head, rest = children
        if rest is not None:
            suffix, tail = rest
        else:
            suffix = tail = ""

        return [
            types.Text(head + suffix),
            types.Text(head + tail),
        ]


class PlainTextParser(ComparisonParser):
    grammar = Grammar(grammars.plain_text_grammar)

    def visit_text(self, node, children):
        return node.text

    def visit_glue(self, node, children):
        return True

    def visit_line(self, node, children):
        predicate, text, *sticky = children
        sticky = self.reduce_children(sticky)
        result = types.Text(text, sticky=bool(sticky), predicate=predicate)
        return result

    def visit_comparison(self, node, children):
        comparison = super().visit_comparison(node, children)
        return types.Predicate(comparison.quality, comparison)


class OperationParser(BaseExpressionParser):
    grammar = Grammar(grammars.operation_grammar)

    def visit_constraint(self, node, children):
        return types.Constraint(node.children[0].text, self.reduce_children(children))

    def visit_operation(self, node, children):
        children = self.reduce_children(children)
        quality, operator, expr = children
        if isinstance(expr, list):
            expr, constraint = expr
        else:
            constraint = None
        return types.Operation(quality, operator, expr, constraint)
