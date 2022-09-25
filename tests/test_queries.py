import textwrap

import pytest

import syml

from ravel import environments
from ravel import queries
from ravel import types

from ravel.compiler.rulebooks import compile_rulebook


class TestQueryPredicates:
    def test_it_should_query_a_set_of_fully_matching_predicates_against_a_query(self):
        query = [("foo", 2), ("bar", 3), ("baz", 4)]
        predicates = [
            types.Predicate("foo", lambda x: x >= 2),
            types.Predicate("bar", lambda x: x >= 3),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is True

    def test_it_should_query_a_set_of_partially_matching_predicates_against_a_query(
        self,
    ):
        query = [("foo", 2), ("bar", 3), ("baz", 4)]
        predicates = [
            types.Predicate("foo", lambda x: x >= 2),
            types.Predicate("bar", lambda x: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query(
        self,
    ):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x: x >= 2),
            types.Predicate("bar", lambda x: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is True

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query_redux(
        self,
    ):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x: x >= 2),
            types.Predicate("bar", lambda x: x > 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False

    def test_it_should_query_with_a_missing_query_and_type_mismatch_on_predicate(self):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x: x >= 2),
            types.Predicate("bar", lambda x: x < "blah"),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False


class TestQueryTop:
    @pytest.fixture
    def rules(self):
        rulebook = syml.loads(TEST_RULES)
        env = environments.Environment()
        return compile_rulebook(env, rulebook)["rulebook"]

    def test_it_should_query_a_rules_database_and_reject_mismatched_rules(self, rules):
        result = queries.query_top("onTest", [("foo", "bar")], rules=rules)
        assert result == ("foo-bar", ["baz"])

    def test_it_should_query_a_rules_database_and_return_the_higher_scoring_rule(
        self, rules
    ):
        result = queries.query_top(
            "onTest", [("foo", "bar"), ("blah", "boo")], rules=rules
        )
        assert result == ("foo-bar-blah-boo", ["blah"])

    def test_it_should_query_a_rules_database_and_return_None_for_no_matches(
        self, rules
    ):
        result = queries.query_top("onTest", [("foo", "blah")], rules=rules)
        assert result is None


TEST_RULES = textwrap.dedent(
    """
    foo-bar:
        - onTest
        - when: foo == "bar"
        - baz

    foo-bar-blah-boo:
        - onTest
        - when:
            - foo = "bar"
            - blah = "boo"
        - blah
"""
)
