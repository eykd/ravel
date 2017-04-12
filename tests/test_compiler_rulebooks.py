from unittest import TestCase
import textwrap

import syml

from ravel import environments
from ravel import exceptions
from ravel import types

from ravel.compiler import rulebooks
from ravel.utils.strings import get_text_source

from .helpers import ensure


class IsWhenTests(TestCase):
    def test_it_should_identify_a_valid_when_clause(self):
        clause = {
            'when': 'foo == 1'
        }
        ensure(rulebooks.is_when(clause)).is_true()

    def test_it_should_reject_invalid_when_clauses(self):
        clause = {
            'when': 'foo == 1',
            'foo': 'bar',
        }
        ensure(rulebooks.is_when(clause)).is_false()
        ensure(rulebooks.is_when('when')).is_false()
        ensure(rulebooks.is_when(['when'])).is_false()


class CompileListOfTextsTests(TestCase):
    def test_it_should_compile_a_sequential_when_clause(self):
        clause = {
            'when': ['foo == 1', 'bar == 2'],
        }
        ensure(rulebooks.get_list_of_texts(clause['when'])).equals(['foo == 1', 'bar == 2'])

    def test_it_should_compile_a_simple_when_clause(self):
        clause = {
            'when': 'foo == 1',
        }
        ensure(rulebooks.get_list_of_texts(clause['when'])).equals(['foo == 1'])


class CompileGivensTests(TestCase):
    def setUp(self):
        self.env = environments.Environment()

    def test_it_should_compile_a_sequential_given_clause(self):
        clause = {
            'given': ['foo = 1', 'bar = 2'],
        }
        (ensure(rulebooks.compile_givens(self.env, clause['given']))
         .equals([
             types.Operation(quality='foo', operator='=', expression=1, constraint=None),
             types.Operation(quality='bar', operator='=', expression=2, constraint=None),
         ]))

    def test_it_should_compile_a_simple_when_clause(self):
        clause = {
            'given': 'foo = 1',
        }
        result = rulebooks.compile_givens(self.env, clause['given'])
        (ensure(result)
         .equals([
             types.Operation(quality='foo', operator='=', expression=1, constraint=None),
         ]))


class CompileAboutTests(TestCase):
    def test_it_should_compile_a_simple_about_clause(self):
        clause = {
            'about': {
                'author': 'Charles Dikkens',
            }
        }
        result = rulebooks.compile_about(clause['about'])
        (ensure(result)
         .equals({'author': 'Charles Dikkens'}))

    def test_it_should_compile_an_about_clause_with_source_objects(self):
        clause = {
            'about': {
                'author': get_text_source('Charles Dikkens', 'Charles Dikkens'),
            }
        }
        result = rulebooks.compile_about(clause['about'])
        (ensure(result)
         .equals({'author': 'Charles Dikkens'}))


class CompileRulebookTests(TestCase):
    def setUp(self):
        self.env = environments.Environment()

    def test_it_should_compile_a_situation_rulebook(self):
        rulebook = syml.loads(TEST_RULEBOOK_SYML, raw=False)
        compiled = rulebooks.compile_rulebook(self.env, rulebook)
        (ensure(compiled)
         .equals(EXPECTED_COMPILED_RULEBOOK))

    def test_it_should_compile_a_situation_with_missing_concept_label(self):
        rulebook_syml = textwrap.dedent("""
            intro:
              - when:
                - Intro == 0

              - Some intro text.
        """)
        result = rulebooks.compile_rulebook(self.env, syml.loads(rulebook_syml, raw=False))
        ensure(result['rulebook']).has_length(1)
        ensure(result['rulebook']).contains('Situation')

    def test_it_should_compile_a_situation_and_add_the_prefix_to_the_location(self):
        rulebook_syml = textwrap.dedent("""
            intro:
              - when:
                - Intro == 0

              - Some intro text.
        """)
        prefix = 'prefix-'
        result = rulebooks.compile_rulebook(self.env, syml.loads(rulebook_syml, raw=False), prefix)
        ensure(result['rulebook']['Situation']['locations']).contains('prefix-intro')

    def test_it_should_fail_to_compile_an_unknown_directive(self):
        bad_rulebook_syml = textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - foo: bar
        """)
        with self.assertRaises(exceptions.ParseError):
            rulebooks.compile_rulebook(self.env, syml.loads(bad_rulebook_syml, raw=False))

    def test_it_should_fail_to_compile_a_multipronged_directive(self):
        bad_rulebook_syml = textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - choice:
                  - foo
                  - bar
                text: This should not be!
        """)
        with self.assertRaises(exceptions.ParseError):
            rulebooks.compile_rulebook(self.env, syml.loads(bad_rulebook_syml, raw=False))

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
        with self.assertRaises(exceptions.ParseError):
            rulebooks.compile_rulebook(self.env, bad_rulebook)


TEST_RULEBOOK_SYML = textwrap.dedent("""
    about:
      author: Me!

    given:
      - [Intro] = 0

    intro:
      - Situation
      - when:
        - [Intro] == 0

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
    'metadata': {'author': 'Me!'},
    'givens': [
        types.Operation(
            quality='Intro',
            operator='=',
            expression=0,
            constraint=None,
        ),
    ],
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
                                comparator = '==',
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
                        types.BeginChoices(),
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
                                    comparator = '>',
                                    expression = 0,
                                ))),
                        types.Text(
                            text = 'What a joke. The number mocked me.',
                            sticky = False,
                            predicate = types.Predicate(
                                name = 'Light',
                                predicate = types.Comparison(
                                    quality = 'Light',
                                    comparator = '>',
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
                        types.BeginChoices(),
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
                            operator='+=',
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
                            operator='+=',
                            expression=1,
                            constraint=None,
                        ),
                    ],
                ),
            },
        },
    }
}
