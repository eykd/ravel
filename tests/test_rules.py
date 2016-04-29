from unittest import TestCase
import ensure

import textwrap

from ravel import types
from ravel import rules
from ravel import yamlish

ensure.unittest_case.maxDiff = None

ensure = ensure.ensure


class TestCompileRulebook(TestCase):
    def test_it_should_compile_a_rulebook(self):
        rulebook = yamlish.YamlParser().parse(TEST_RULEBOOK_YAMLISH).as_data()
        compiled = rules.compile_rulebook(rulebook)
        (ensure(compiled)
         .equals(EXPECTED_COMPILED_RULEBOOK))


TEST_RULEBOOK_YAMLISH = textwrap.dedent("""
    # rulebook
    # rule name
    foo-bar:
        # concept
        - onTest
        # ruleset
        - when:
            - foo == "bar"
        # baggage
        - balogna
    # rule name
    baz-barf-blah-boo:
        # concept
        - onTest
        # ruleset
        - when:
            - baz == "barf"
            - blah == "boo"
        # baggage
        - baloney
""")


EXPECTED_COMPILED_RULEBOOK = {
    'onTest': [
        types.Rule(
            name = 'baz-barf-blah-boo',
            predicates = [
                types.Predicate(
                    name = 'baz',
                    predicate = types.Comparison(
                        quality = 'baz',
                        comparison = '==',
                        expression = 'barf',
                    )
                ),
                types.Predicate(
                    name = 'blah',
                    predicate = types.Comparison(
                        quality = 'blah',
                        comparison = '==',
                        expression = 'boo',
                    )
                ),
            ],
            baggage = ['baloney']
        ),
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
            baggage = ['balogna']
        ),
    ],
}
