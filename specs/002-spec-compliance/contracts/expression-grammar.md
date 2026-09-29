# Contract: Expression grammar (FR-001 – FR-007)

**Surface**: `ravel.grammars.base_expression_grammar` (shared by `operation_grammar`,
`comparison_grammar`, `plain_text_grammar`) and the visitors in `ravel.parsers`
(`BaseExpressionParser`, `OperationParser`, `ComparisonParser`, `PlainTextParser`).

**Acceptance criterion on every task that edits `grammars.py`** (PD-17): every regex backslash in
the grammar text is doubled (`\\s`, `\\d`, `\\w`, `\\W`, `\\b`, `\\[`, `\\]`), `plain_text_grammar`'s
`"\n"` stays single, and `uv run pytest tests/test_grammars.py` passes.

## Grammar (replaces the expression half of `base_expression_grammar`)

Shown with the doubled backslashes the source needs. Subject (`quality`), `setter`, `comparator`,
`ws` and `end` are unchanged.

```peg
expression        = additive
additive          = multiplicative (ws? additive_op ws? multiplicative)*
multiplicative    = primary (ws? multiplicative_op ws? primary)*
additive_op       = add / subtract
multiplicative_op = multiply / floor_div / divide / modulus
primary           = term / (open_paren ws? expression ws? close_paren)
term              = number / string / qvalue / quality_ref

qvalue            = ~"value\\b"
quality_ref       = bracketed_quality / identifier
identifier        = ~"(?!(?:value|min|max)\\b)[^\\W\\d]\\w*"

number            = float / integer
float             = ~"-?\\d+\\.\\d*"
integer           = ~"-?\\d+"

string            = ('"""' ~'[^"]*' '"""') / ("'''" ~"[^']*" "'''") / ("```" ~"[^`]*" "```")
                  / ('"' ~'[^"]*' '"')     / ("'" ~"[^']*" "'")     / ("`" ~"[^`]*" "`")

constraint        = (max / min) ws number
```

`ComparisonParser.grammar` becomes `Grammar(grammars.comparison_grammar)` (today it's rebuilt
inline from a copy of the rule text).

## Visitor signatures (`ravel.parsers`)

```python
class BaseExpressionParser(BaseParser):
    def visit_additive(self, node, children) -> Term: ...  # left fold
    def visit_multiplicative(self, node, children) -> Term: ...  # left fold
    def visit_identifier(self, node, children) -> types.QualityRef: ...
    def visit_quality_ref(self, node, children) -> types.QualityRef: ...  # wraps bracketed names
    def visit_qvalue(self, node, children) -> types.Value: ...  # returns types.VALUE
    def visit_string(self, node, children) -> str: ...  # "" allowed


class OperationParser(BaseExpressionParser):
    def visit_operation(self, node, children) -> types.Operation:
        """Raises OperationParseError for a constraint on a string literal."""
```

`visit_bracketed_quality` keeps returning the bare name (the subject rule still uses it);
`visit_quality_ref` wraps it in `QualityRef`. The left fold:

```python
def _fold_left(first: Term, rest: list[tuple[str, Term]]) -> Term:
    result = first
    for operator, operand in rest:
        result = types.Expression(result, operator, operand)
    return result
```

## Examples: `.ravel` text → compiled value

`OperationParser().parse(text)`:

| Input | Output |
|---|---|
| `X = 10 - 4 - 2` | `Operation("X", "=", Expression(Expression(10, "-", 4), "-", 2))` |
| `X = 8 / 4 / 2` | `Operation("X", "=", Expression(Expression(8, "/", 4), "/", 2))` |
| `X = 2 + 3 * 4` | `Operation("X", "=", Expression(2, "+", Expression(3, "*", 4)))` |
| `X = 8 // 2 * 3 % 5` | `Operation("X", "=", Expression(Expression(Expression(8, "//", 2), "*", 3), "%", 5))` |
| `X = (1 + 2) * 3` | `Operation("X", "=", Expression(Expression(1, "+", 2), "*", 3))` |
| `X = -5` | `Operation("X", "=", -5)` |
| `X = -1.5` | `Operation("X", "=", -1.5)` |
| `X = 10-4` | `Operation("X", "=", Expression(10, "-", 4))` |
| `X = 10 -4` | `Operation("X", "=", Expression(10, "-", 4))` |
| `X = 10 - -4` | `Operation("X", "=", Expression(10, "-", -4))` |
| `X = ""` | `Operation("X", "=", "")` |
| `X = [Health] + Bonus` | `Operation("X", "=", Expression(QualityRef("Health"), "+", QualityRef("Bonus")))` |
| `X = Health + 1` | `Operation("X", "=", Expression(QualityRef("Health"), "+", 1))` |
| `X += value * 2` | `Operation("X", "+=", Expression(VALUE, "*", 2))` |
| `X = values` | `Operation("X", "=", QualityRef("values"))` |
| `X = maxHealth` | `Operation("X", "=", QualityRef("maxHealth"))` |
| `X = Été + 1` | `Operation("X", "=", Expression(QualityRef("Été"), "+", 1))` |
| `X -= 10 min 0` | `Operation("X", "-=", 10, Constraint("min", 0))` |
| `X += 1 max -5` | `Operation("X", "+=", 1, Constraint("max", -5))` |
| `X = Health max 3` | `Operation("X", "=", QualityRef("Health"), Constraint("max", 3))` |
| `value = 3` | `Operation("value", "=", 3)` |
| `"Wearing Cloak" = 0` | `Operation("Wearing Cloak", "=", 0)` |
| `[Has Key] = 1` | `Operation("Has Key", "=", 1)` |

`ComparisonParser().parse(text)`:

| Input | Output |
|---|---|
| `Health > -1` | `Comparison("Health", ">", -1)` |
| `Name == "Wearing Cloak"` | `Comparison("Name", "==", "Wearing Cloak")` (a string) |
| `X == [Y]` | `Comparison("X", "==", QualityRef("Y"))` (**was** the string `"Y"`) |
| `"Wearing Cloak" >= 1` | `Comparison("Wearing Cloak", ">=", 1)` |
| `Score > value` | `Comparison("Score", ">", VALUE)` |

Rejected (raise `parsimonious` `ParseError`/`IncompleteParseError`; the compiler wraps them in
`ComparisonParseError`/`OperationParseError` with the source position):

| Input | Why |
|---|---|
| `X=5`, `X>1` | R8: whitespace required around setters and comparators |
| `X += 1 min 0 max 8` | one constraint per operation |
| `X += 1 max value` | a bound is a number literal (PD-07) |
| `X = -Health`, `X = -(1 + 2)` | no unary minus on references or groups (PD-02) |
| `X = min + 1`, `X = max` | reserved inside expressions (R4) |

Raised by the visitor (`OperationParseError`, message names the operation text):

| Input | Why |
|---|---|
| `X = "a" max 3` | constraint on a string literal (PD-08) |

## Expected edits to existing tests

`tests/test_parsers.py::TestOperationsParser`:

- `test_it_should_handle_a_more_complicated_expressions`: `3 + 2 + 3` becomes
  `Expression(Expression(3, "+", 2), "+", 3)`.
- `test_it_should_handle_a_complex_expression`: `3 + 5 * 2 / (3 - 2)` becomes
  `Expression(3, "+", Expression(Expression(5, "*", 2), "/", Expression(3, "-", 2)))`.
