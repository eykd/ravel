from typing import Final

from parsimonious import Grammar, NodeVisitor

from ravel import exceptions, grammars, types

# Expression trees are left-deep, and Expression.evaluate recurses through them. Cap the operands in one
# chain well below the interpreter's recursion limit so a hostile rulebook fails at compile time with a
# typed ParseError instead of a raw RecursionError at runtime. Additive and multiplicative chains nest
# (a multiplicative chain is one additive operand), so the worst-case depth is about twice the cap.
MAX_EXPRESSION_OPERANDS: Final = 100


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
    unwrapped_exceptions = (exceptions.ParseError,)
    operand_limit_error: type[exceptions.ParseError] = exceptions.ParseError
    visit_setter = BaseParser.get_text
    visit_simple_quality = BaseParser.get_text

    def visit_quoted_quality(self, node, children):
        return node.text[1:-1]

    def visit_bracketed_quality(self, node, children):
        return node.text[1:-1]

    def visit_identifier(self, node, children):
        return types.QualityRef(node.text)

    def visit_quality_ref(self, node, children):
        name = children[0]
        return name if isinstance(name, types.QualityRef) else types.QualityRef(name)

    def visit_float(self, node, children):
        return float(node.text)

    def visit_integer(self, node, children):
        return int(node.text)

    def visit_string(self, node, children):
        return node.children[0].children[1].text

    def visit_qvalue(self, node, children):
        return types.VALUE

    def _fold_left(self, node, children):
        first, rest = children
        if rest is None:
            rest = []
        elif isinstance(rest[0], str):
            rest = [rest]
        if len(rest) + 1 > MAX_EXPRESSION_OPERANDS:
            raise self.operand_limit_error(
                "Expression has %d operands; the maximum supported is %d" % (len(rest) + 1, MAX_EXPRESSION_OPERANDS)
            )
        result = first
        for operator, operand in rest:
            result = types.Expression(result, operator, operand)
        return result

    visit_additive = visit_multiplicative = _fold_left

    visit_additive_op = visit_multiplicative_op = BaseParser.get_text

    visit_add = visit_subtract = BaseParser.get_text
    visit_multiply = BaseParser.get_text
    visit_floor_div = visit_divide = visit_modulus = BaseParser.get_text


class ComparisonParser(BaseExpressionParser):
    operand_limit_error = exceptions.ComparisonParseError
    grammar = Grammar(grammars.comparison_grammar)

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
    operand_limit_error = exceptions.OperationParseError
    grammar = Grammar(grammars.operation_grammar)

    def parse(self, text, pos=0):
        """Parse an operation, reporting any malformed one as an OperationParseError naming the text."""
        try:
            return super().parse(text, pos=pos)
        except exceptions.ParsimoniousParseError as e:
            raise exceptions.OperationParseError("Invalid operation %r: %s" % (text, e)) from e

    def visit_constraint(self, node, children):
        return types.Constraint(node.children[0].text, self.reduce_children(children))

    def visit_operation(self, node, children):
        children = self.reduce_children(children)
        quality, operator, expr = children
        if isinstance(expr, list):
            expr, constraint = expr
        else:
            constraint = None
        if constraint is not None and isinstance(expr, str):
            raise exceptions.OperationParseError(
                "Invalid operation %r: a constraint cannot apply to a string literal" % node.text.strip()
            )
        return types.Operation(quality, operator, expr, constraint)
