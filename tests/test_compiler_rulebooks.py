from unittest import TestCase

import textwrap

from ravel import exceptions
from ravel import types

from ravel.compiler import yamlish

from ravel.compiler.rulebooks import compile_rulebook

from .helpers import ensure


class CompileRulebookTests(TestCase):
    def test_it_should_compile_a_situation_rulebook(self):
        compiled = compile_rulebook(yamlish.parse(TEST_RULEBOOK_YAMLISH))
        (ensure(compiled)
         .equals(EXPECTED_COMPILED_RULEBOOK))

    def test_it_should_compile_a_situation_with_missing_concept_label(self):
        rulebook_yamlish = textwrap.dedent("""
            intro:
              - when:
                - Intro == 0

              - Some intro text.
        """)
        result = compile_rulebook(yamlish.parse(rulebook_yamlish))
        ensure(result['rulebook']).has_length(1)
        ensure(result['rulebook']).contains('Situation')

    def test_it_should_compile_a_situation_and_add_the_prefix_to_the_location(self):
        rulebook_yamlish = textwrap.dedent("""
            intro:
              - when:
                - Intro == 0

              - Some intro text.
        """)
        prefix = 'prefix-'
        result = compile_rulebook(yamlish.parse(rulebook_yamlish), prefix)
        ensure(result['rulebook']['Situation']['locations']).contains('prefix-intro')

    def test_it_should_fail_to_compile_an_unknown_directive(self):
        bad_rulebook_yamlish = textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - foo: bar
        """)
        (ensure(compile_rulebook)
         .called_with(yamlish.parse(bad_rulebook_yamlish))
         .raises(exceptions.ParseError))

    def test_it_should_fail_to_compile_a_multipronged_directive(self):
        bad_rulebook_yamlish = textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - choice:
                  - foo
                  - bar
                text: This shouldn't be!
        """)
        (ensure(compile_rulebook)
         .called_with(yamlish.parse(bad_rulebook_yamlish))
         .raises(exceptions.ParseError))

    def test_it_should_fail_to_compile_with_missing_intro_text(self):
        bad_rulebook = {
            'intro': [
                'Situation',
                {
                    'when': [
                        'Intro == 0',
                    ],
                },
                {'foo': 'bar'}
            ]
        }
        (ensure(compile_rulebook)
         .called_with(bad_rulebook)
         .raises(exceptions.ParseError))

TEST_RULEBOOK_YAMLISH = textwrap.dedent("""
    intro:
      - Situation
      - when:
        - Intro == 0

      - It was raining steadily by the time I dropped my last rider off[...] and swung by the post office on my way home.
      - choice:
        - The post office was closed[.], but I let myself in to the PO box room.
        - The fluorescent glare hurt my eyes after the evening of headlight
          glare.
        - choice:
          - I quietly cursed the light, wishing for the dark.
          - effect: Dark += 1
        - choice:
          - I quietly gave thanks for the light.
          - effect: Light += 1
      - I found my box, lucky 1313. <>
      - {Dark > 0}What a lovely number.
      - {Light > 0}What a joke. The number mocked me.
""")


EXPECTED_COMPILED_RULEBOOK = {
    'includes': [],
    'rulebook': {
        'Situation': {
            'rules': [
                types.Rule(
                    name = 'intro',
                    predicates = [
                        types.Predicate(
                            name = 'Intro',
                            predicate = types.Comparison(
                                quality = 'Intro',
                                comparison = '==',
                                expression = 0,
                            )
                        ),
                    ],
                )
            ],
            'locations': {
                'intro': types.Situation(
                    intro = types.Text(
                        text = 'It was raining steadily by the time I dropped my last rider off...',
                        sticky = False,
                        predicate = None,
                    ),
                    directives = [
                        types.Text(
                            text = ('It was raining steadily by the time I dropped my last rider '
                                    'off and swung by the post office on my way home.'),
                            sticky = False,
                            predicate = None,
                        ),
                        types.Choice(
                            choice = 'intro::the-post-office-was-closed',
                        ),
                        types.GetChoice(),
                        types.Text(
                            text = 'I found my box, lucky 1313. ',
                            sticky = True,
                            predicate = None,
                        ),
                        types.Text(
                            text = 'What a lovely number.',
                            sticky = False,
                            predicate = types.Predicate(
                                name = 'Dark',
                                predicate = types.Comparison(
                                    quality = 'Dark',
                                    comparison = '>',
                                    expression = 0,
                                ))),
                        types.Text(
                            text = 'What a joke. The number mocked me.',
                            sticky = False,
                            predicate = types.Predicate(
                                name = 'Light',
                                predicate = types.Comparison(
                                    quality = 'Light',
                                    comparison = '>',
                                    expression = 0,
                                ))),
                    ],
                ),
                'intro::the-post-office-was-closed': types.Situation(
                    intro = types.Text(
                        text = 'The post office was closed.',
                        sticky = False,
                        predicate = None,
                    ),
                    directives = [
                        types.Text(
                            text = 'The post office was closed, but I let myself in to the PO box room.',
                            sticky = False,
                            predicate = None,
                        ),
                        types.Text(
                            text = ('The fluorescent glare hurt my eyes after the evening '
                                    'of headlight glare.'),
                            sticky = False,
                            predicate = None,
                        ),
                        types.Choice(
                            choice = 'intro::i-quietly-cursed-the-light-wishing-for-the-dark',
                        ),
                        types.Choice(
                            choice ='intro::i-quietly-gave-thanks-for-the-light',
                        ),
                        types.GetChoice(),
                    ],
                ),
                'intro::i-quietly-cursed-the-light-wishing-for-the-dark': types.Situation(
                    intro = types.Text(
                        text = 'I quietly cursed the light, wishing for the dark.',
                        sticky = False,
                        predicate = None,
                    ),
                    directives = [
                        types.Text(
                            text = 'I quietly cursed the light, wishing for the dark.',
                            sticky = False,
                            predicate = None,
                        ),
                        types.Operation(
                            quality='Dark',
                            operation='+=',
                            expression=1,
                            constraint=None,
                        ),
                    ],
                ),
                'intro::i-quietly-gave-thanks-for-the-light': types.Situation(
                    intro = types.Text(
                        text = 'I quietly gave thanks for the light.',
                        sticky = False,
                        predicate = None,
                    ),
                    directives = [
                        types.Text(
                            text = 'I quietly gave thanks for the light.',
                            sticky = False,
                            predicate = None,
                        ),
                        types.Operation(
                            quality='Light',
                            operation='+=',
                            expression=1,
                            constraint=None,
                        ),
                    ],
                ),
            },
        },
    }
}
