from unittest import TestCase
import ensure

import textwrap

from ravel.comparisons import Comparison
from ravel.predicates import Predicate
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
    ### rulebook

    ## common ruleset
    when:
        - blue == "blargh"
        - blark == 'floogle'

    ## rule
    # rule name
    foo-bar:
        # concept
        - onTest
        # ruleset
        - when:
            - foo == "bar"
        # baggage
        - balogna
    ## rule
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
    'onTest': {
        'rules': [
            rules.Rule(
                name = 'baz-barf-blah-boo',
                predicates = [
                    Predicate(
                        name = 'baz',
                        predicate = Comparison(
                            quality = 'baz',
                            comparison = '==',
                            expression = 'barf',
                        )
                    ),
                    Predicate(
                        name = 'blah',
                        predicate = Comparison(
                            quality = 'blah',
                            comparison = '==',
                            expression = 'boo',
                        )
                    ),
                    Predicate(
                        name = 'blark',
                        predicate = Comparison(
                            quality = 'blark',
                            comparison = '==',
                            expression = 'floogle',
                        )
                    ),
                    Predicate(
                        name = 'blue',
                        predicate = Comparison(
                            quality = 'blue',
                            comparison = '==',
                            expression = 'blargh',
                        )
                    ),
                ],
            ),
            rules.Rule(
                name = 'foo-bar',
                predicates = [
                    Predicate(
                        name = 'blark',
                        predicate = Comparison(
                            quality = 'blark',
                            comparison = '==',
                            expression = 'floogle',
                        )
                    ),
                    Predicate(
                        name = 'blue',
                        predicate = Comparison(
                            quality = 'blue',
                            comparison = '==',
                            expression = 'blargh',
                        )
                    ),
                    Predicate(
                        name = 'foo',
                        predicate = Comparison(
                            quality = 'foo',
                            comparison = '==',
                            expression = 'bar'
                        )
                    ),
                ],
            ),
        ],
        'locations': {
            'baz-barf-blah-boo': ['baloney'],
            'foo-bar': ['balogna'],
        }
    }
}
