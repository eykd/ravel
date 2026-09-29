import pytest

from ravel import types
from ravel.compiler.rulesets import compile_ruleset, predicate_sort_key

from .helpers import source


class TestCompileRuleset:
    def test_it_should_compile_predicates_in_a_list_ruleset(self, env):
        result = compile_ruleset(
            env,
            "test-concept",
            "test-rule",
            [
                source('"foo" == 9'),
                source("bar < 5"),
                source('blah == "boo"'),
            ],
        )

        expected = [
            types.Predicate(
                name="bar",
                predicate=types.Comparison(quality="bar", comparator="<", expression=5),
            ),
            types.Predicate(
                name="blah",
                predicate=types.Comparison(quality="blah", comparator="==", expression="boo"),
            ),
            types.Predicate(
                name="foo",
                predicate=types.Comparison(quality="foo", comparator="==", expression=9),
            ),
        ]

        assert result == expected


class TestMixedTypePredicateOrdering:
    """Predicates on one quality and comparator may mix operand types; sorting must not raise."""

    @pytest.mark.parametrize(
        "targets",
        [
            ["x > 1", "x > y"],
            ["x > 1", 'x > "a"'],
            ["x > 1.5", "x > value"],
            ["x > 1 - y", "x > 2", "x > value", 'x > "a"', "x > y", "x > 1 - z", "x > y - 2", "x > 0.5"],
        ],
    )
    def test_it_should_order_mixed_type_operands_regardless_of_input_order(self, env, targets):
        forward = compile_ruleset(env, "c", "r", [source(t) for t in targets])
        backward = compile_ruleset(env, "c", "r", [source(t) for t in reversed(targets)])

        assert forward == backward
        assert len(forward) == len(targets)

    def test_it_should_order_same_typed_operands_naturally(self, env):
        result = compile_ruleset(
            env, "c", "r", [source(t) for t in ("x > 10", "x > 2.5", "x > 2", 'x > "b"', 'x > "a"')]
        )

        assert [p.predicate.expression for p in result] == [2, 2.5, 10, "a", "b"]

    def test_it_should_order_by_quality_then_comparator_before_operand(self, env):
        result = compile_ruleset(env, "c", "r", [source(t) for t in ("y > 1", "x < 9", "x > y", "x > 1")])

        assert [(p.name, p.predicate.comparator) for p in result] == [("x", "<"), ("x", ">"), ("x", ">"), ("y", ">")]

    def test_it_should_give_an_unknown_operand_type_a_repr_based_key(self):
        odd = types.Predicate("x", types.Comparison("x", ">", object))

        assert predicate_sort_key(odd)[3][0] == 5
