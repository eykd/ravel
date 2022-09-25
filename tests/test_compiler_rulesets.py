from ravel import environments
from ravel import types

from ravel.compiler.rulesets import compile_ruleset

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
                predicate=types.Comparison(
                    quality="blah", comparator="==", expression="boo"
                ),
            ),
            types.Predicate(
                name="foo",
                predicate=types.Comparison(
                    quality="foo", comparator="==", expression=9
                ),
            ),
        ]

        assert result == expected
