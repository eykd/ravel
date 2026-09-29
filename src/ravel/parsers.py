import re
import sys
from typing import Final

from parsimonious import Grammar, NodeVisitor

from ravel import exceptions, grammars, types

# Expression trees are left-deep, and Expression.evaluate recurses through them. Cap the operands in one
# chain well below the interpreter's recursion limit so a hostile rulebook fails at compile time with a
# typed ParseError instead of a raw RecursionError at runtime. Additive and multiplicative chains nest
# (a multiplicative chain is one additive operand), so the worst-case depth is about twice the cap.
MAX_EXPRESSION_OPERANDS: Final = 100

# Parentheses let capped chains nest, so the operand cap alone does not bound tree depth. Cap the total
# depth of an expression tree (the worst accepted shape, a full additive chain whose operand is a full
# multiplicative chain, is about 200 deep and evaluates fine) and cap parenthesis nesting before
# Parsimonious recurses through it, which would overflow the stack from a few hundred levels.
MAX_EXPRESSION_DEPTH: Final = 200
MAX_PAREN_DEPTH: Final = 20

# The caps above run in the visitor, after Parsimonious has built the whole packrat parse tree, so they
# bound evaluator recursion but not parser CPU or memory (a 200 KB chain cost seconds and hundreds of MB
# before rejection). Refuse over-long expression text before parsing at all. 64 KiB comfortably admits a
# full operand chain of 100 operands with 100-character quality names (about 10 KB) and matches the
# string-length cap. Only expression parsers are gated; long prose lines are legitimate and cheap.
MAX_EXPRESSION_LENGTH: Final = 65_536


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
    max_length: int | None = MAX_EXPRESSION_LENGTH
    visit_setter = BaseParser.get_text
    visit_simple_quality = BaseParser.get_text

    def parse(self, text, pos=0):
        """Parse text, refusing over-long text or over-deep parentheses before the grammar can build a tree."""
        if self.max_length is not None and len(text) > self.max_length:
            raise self.operand_limit_error(
                "Expression is %d characters long; the maximum supported is %d" % (len(text), self.max_length)
            )
        depth = deepest = 0
        for char in text:
            if char == "(":
                depth += 1
                deepest = max(deepest, depth)
            elif char == ")":
                depth = max(depth - 1, 0)
        if deepest > MAX_PAREN_DEPTH:
            raise self.operand_limit_error(
                "Expression nests parentheses %d deep; the maximum supported is %d" % (deepest, MAX_PAREN_DEPTH)
            )
        self._depths: dict[int, int] = {}
        return super().parse(text, pos=pos)

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
        try:
            return int(node.text)
        except ValueError as e:
            raise self.operand_limit_error(
                "Integer literal has too many digits (%d); the maximum supported is %d"
                % (len(node.text.lstrip("-")), sys.get_int_max_str_digits())
            ) from e

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
        depth = self._depths.get(id(first), 0)
        for operator, operand in rest:
            result = types.Expression(result, operator, operand)
            depth = 1 + max(depth, self._depths.get(id(operand), 0))
        if depth > MAX_EXPRESSION_DEPTH:
            raise self.operand_limit_error(
                "Expression is nested %d deep; the maximum supported is %d" % (depth, MAX_EXPRESSION_DEPTH)
            )
        self._depths[id(result)] = depth
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
    # Prose is not an expression, so the whole line is exempt from the length cap; only the leading
    # {...} predicate prefix is an expression, and parse() gates its length before the grammar runs.
    max_length = None
    grammar = Grammar(grammars.plain_text_grammar)

    # The prefix text after the opening brace: runs to the first "}" outside a quoted string (strings may
    # hold a "}"), or to the end of the line when the brace is never closed. Each branch starts on a
    # different character and the star cannot fail, so the scan is linear with no backtracking.
    _prefix_span = re.compile(r"""\{((?:"[^"]*"|'[^']*'|`[^`]*`|[^}])*)""")

    def parse(self, text, pos=0):
        """Parse a text line, refusing an over-long {...} prefix (or unclosed brace) before the grammar runs."""
        match = self._prefix_span.match(text, pos)
        if match is not None and len(match.group(1)) > MAX_EXPRESSION_LENGTH:
            raise exceptions.ComparisonParseError(
                "Predicate is %d characters long; the maximum supported is %d"
                % (len(match.group(1)), MAX_EXPRESSION_LENGTH)
            )
        return super().parse(text, pos=pos)

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
            raise exceptions.OperationParseError(
                "Invalid operation %s: %s" % (exceptions.bounded_repr(text), exceptions.printable(e))
            ) from e

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
                "Invalid operation %s: a constraint cannot apply to a string literal"
                % exceptions.bounded_repr(node.text.strip())
            )
        return types.Operation(quality, operator, expr, constraint)
