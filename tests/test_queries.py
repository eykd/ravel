from unittest import TestCase
import ensure

import textwrap

from ravel import queries
from ravel import types

from ravel.compiler import yamlish

from ravel.compiler.rulebooks import compile_rulebook

ensure.unittest_case.maxDiff = None

ensure = ensure.ensure


class QueryPredicatesTest(TestCase):
    def test_it_should_query_a_set_of_fully_matching_predicates_against_a_query(self):
        query = [('foo', 2), ('bar', 3), ('baz', 4)]
        predicates = [
            types.Predicate('foo', lambda x: x >= 2),
            types.Predicate('bar', lambda x: x >= 3),
        ]
        matched = queries.query_predicates(query, predicates)
        ensure(matched).is_true()

    def test_it_should_query_a_set_of_partially_matching_predicates_against_a_query(self):
        query = [('foo', 2), ('bar', 3), ('baz', 4)]
        predicates = [
            types.Predicate('foo', lambda x: x >= 2),
            types.Predicate('bar', lambda x: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        ensure(matched).is_false()

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query(self):
        query = [('foo', 2), ('baz', 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate('foo', lambda x: x >= 2),
            types.Predicate('bar', lambda x: x < 2),
        ]
        matched = queries.query_predicates(query, predicates)
        ensure(matched).is_true()

    def test_it_should_query_a_set_of_partially_matching_predicates_with_missing_query_redux(self):
        query = [('foo', 2), ('baz', 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate('foo', lambda x: x >= 2),
            types.Predicate('bar', lambda x: x > 2),
        ]
        matched = queries.query_predicates(query, predicates)
        ensure(matched).is_false()

    def test_it_should_query_with_a_missing_query_and_type_mismatch_on_predicate(self):
        query = [('foo', 2), ('baz', 4)]  # 'bar' is effectively 0
        predicates = [
            types.Predicate('foo', lambda x: x >= 2),
            types.Predicate('bar', lambda x: x < 'blah'),
        ]
        matched = queries.query_predicates(query, predicates)
        ensure(matched).is_false()


class QueryTopTest(TestCase):
    def setUp(self):
        rulebook = yamlish.YamlParser().parse(TEST_RULES).as_data()
        self.rules = compile_rulebook(rulebook)['rulebook']

    def test_it_should_query_a_rules_database_and_reject_mismatched_rules(self):
        result = queries.query_top('onTest', [('foo', 'bar')], rules=self.rules)
        ensure(result).equals(['baz'])

    def test_it_should_query_a_rules_database_and_return_the_higher_scoring_rule(self):
        result = queries.query_top('onTest', [('foo', 'bar'), ('blah', 'boo')], rules=self.rules)
        ensure(result).equals(['blah'])

    def test_it_should_query_a_rules_database_and_return_None_for_no_matches(self):
        result = queries.query_top('onTest', [('foo', 'blah')], rules=self.rules)
        ensure(result).is_none()


TEST_RULES = textwrap.dedent("""
    foo-bar:
        - onTest
        - when:
            - foo == "bar"
        - baz

    foo-bar-blah-boo:
        - onTest
        - when:
            - foo == "bar"
            - blah == "boo"
        - blah
""")
