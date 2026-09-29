import textwrap

import pytest
import syml

from ravel import environments, loaders, queries, types
from ravel.compiler.rulebooks import compile_rulebook


class TestQueryPredicates:
    def test_it_should_query_a_set_of_fully_matching_predicates_against_a_query(self):
        query = [("foo", 2), ("bar", 3), ("baz", 4)]
        predicates = [
            types.Predicate("foo", lambda x, qualities=None: x >= 2),
            types.Predicate("bar", lambda x, qualities=None: x >= 3),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is True

    def test_it_should_query_a_set_of_partially_matching_predicates_against_a_query(
        self,
    ):
        query = [("foo", 2), ("bar", 3), ("baz", 4)]
        predicates = [
            types.Predicate("foo", lambda x, qualities=None: x >= 2),
            types.Predicate("bar", lambda x, qualities=None: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query(
        self,
    ):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x, qualities=None: x >= 2),
            types.Predicate("bar", lambda x, qualities=None: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is True

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query_redux(
        self,
    ):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x, qualities=None: x >= 2),
            types.Predicate("bar", lambda x, qualities=None: x > 2),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False

    def test_it_should_query_with_a_missing_query_and_type_mismatch_on_predicate(self):
        query = [("foo", 2), ("baz", 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate("foo", lambda x, qualities=None: x >= 2),
            types.Predicate("bar", types.Comparison("bar", "<", "blah")),
        ]
        matched = queries.query_predicates(query, predicates)
        assert matched is False


class TestQueryPredicatesQualitiesLookup:
    @staticmethod
    def _predicate(quality, comparator, expression):
        return types.Predicate(quality, types.Comparison(quality, comparator, expression))

    def test_it_should_pass_the_qualities_lookup_to_a_set_subject_predicate(self):
        predicates = [self._predicate("X", ">", types.QualityRef("Y"))]
        assert queries.query_predicates([("X", 2), ("Y", 1)], predicates) is True
        assert queries.query_predicates([("X", 2), ("Y", 3)], predicates) is False

    def test_it_should_pass_the_qualities_lookup_to_an_unset_subject_predicate(self):
        predicates = [self._predicate("X", "<", types.QualityRef("Y"))]
        assert queries.query_predicates([("Y", 5)], predicates) is True

    def test_it_should_treat_division_by_an_unset_quality_as_a_non_match(self):
        predicates = [
            self._predicate("X", ">", types.Expression(10, "/", types.QualityRef("Y"))),
        ]
        assert queries.query_predicates([("X", 5)], predicates) is False

    def test_it_should_treat_a_text_comparison_against_a_number_as_a_non_match(self):
        predicates = [self._predicate("X", ">", types.QualityRef("Name"))]
        assert queries.query_predicates([("Name", "a"), ("X", 1)], predicates) is False

    def test_it_should_still_match_other_rules_when_one_predicate_is_unevaluable(self):
        broken = [self._predicate("X", ">", types.Expression(10, "/", types.QualityRef("Y")))]
        working = [self._predicate("X", ">", types.QualityRef("Z"))]
        q = [("X", 5), ("Z", 1)]
        assert queries.query_predicates(q, broken) is False
        assert queries.query_predicates(q, working) is True


class TestQueryTop:
    @pytest.fixture
    def rules(self):
        rulebook = syml.loads(TEST_RULES)
        env = environments.Environment(loader=loaders.MemoryLoader({}))
        return compile_rulebook(env, rulebook)["rulebook"]

    def test_it_should_query_a_rules_database_and_reject_mismatched_rules(self, rules):
        result = queries.query_top("onTest", [("foo", "bar")], rules=rules)
        assert result == ("foo-bar", ["baz"])

    def test_it_should_query_a_rules_database_and_return_the_higher_scoring_rule(self, rules):
        result = queries.query_top("onTest", [("foo", "bar"), ("blah", "boo")], rules=rules)
        assert result == ("foo-bar-blah-boo", ["blah"])

    def test_it_should_query_a_rules_database_and_return_None_for_no_matches(self, rules):
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
