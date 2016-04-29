from unittest import TestCase
from ensure import ensure

import textwrap

from ravel import types
from ravel import rules


TEST_RULEBOOK_YAMLISH = textwrap.dedent("""
    foo-bar:
        - onTest
        - when:
            - foo == bar
        - baz
    foo-bar-blah-boo:
        - onTest
        - when:
            - foo == "bar"
            - blah == "boo"
        - blah
""")

TEST_RULEBOOK = {                  # rulebook
    'foo-bar': [                   # rule name
        'onTest',                  # concept
        {'when': ['foo == "bar"']},# ruleset
        'baz'                      # baggage
    ],
    'foo-bar-blah-boo': [
        'onTest',
        {'when': [
            'foo == "bar"',
            'blah == "boo"'
        ]},
        'blah'
    ],
}


EXPECTED_COMPILED_RULEBOOK = {
    'onTest': [
        types.Rule(
            name = 'foo-bar',
            predicates = [
                types.Predicate(
                    name = 'foo',
                    predicate = types.Comparison(
                        quality = 'foo',
                        comparison = '==',
                        expression = 'bar'
                    )
                ),
            ],
            baggage = ['baz']
        ),
        types.Rule(
            name = 'foo-bar-blah-boo',
            predicates = [
                types.Predicate(
                    name = 'blah',
                    predicate = types.Comparison(
                        quality = 'blah',
                        comparison = '==',
                        expression = 'boo',
                    )
                ),
                types.Predicate(
                    name = 'foo',
                    predicate = types.Comparison(
                        quality = 'foo',
                        comparison = '==',
                        expression = 'bar',
                    )
                ),
            ],
            baggage = ['blah']
        ),
    ],
}


class TestCompileRulebook(TestCase):
    def test_it_should_compile_a_rulebook(self):
        (ensure(rules.compile_rulebook)
         .called_with(TEST_RULEBOOK)
         .equals(EXPECTED_COMPILED_RULEBOOK))

        # result = rules.compile_rulebook(TEST_RULES)
        # expected = EXPECTED_COMPILED_RULEBOOK
        # ensure(result).is_a(dict).of(str).to(list)
        # ensure(result).has_length(1)
        # ensure(result['onTest']).is_a(list).of(rules.Rule)
        # ensure(result['onTest']).has_length(2)

        # item = result['onTest'][0]
        # ensure(item.name).equals('foo-bar')
        # ensure(item.predicates).has_length(1)
        # ensure(item.predicates[0].name).equals('foo')
        # ensure(item.predicates[0].predicate).called_with('bar').is_true()
        # ensure(item.baggage).equals(['baz'])

        # item = result['onTest'][1]
        # ensure(item.name).equals('foo-bar-blah-boo')
        # ensure(item.predicates).has_length(2)
        # ensure(item.predicates[0].name).equals('blah')
        # ensure(item.predicates[0].predicate).called_with('boo').is_true()
        # ensure(item.predicates[1].name).equals('foo')
        # ensure(item.predicates[1].predicate).called_with('bar').is_true()
        # ensure(item.baggage).equals(['blah'])
