from unittest import TestCase

from pprint import pprint
import textwrap

import ensure
from ensure import EnsureError
from deepdiff import DeepDiff

from ravel.comparisons import Comparison
from ravel.predicates import Predicate
from ravel import rules
from ravel import yamlish
from ravel.concepts import situations

ensure.unittest_case.maxDiff = None
ensure = ensure.ensure


class TextTests(TestCase):
    pass


class IntroTextParserTests(TestCase):
    def setUp(self):
        self.parser = situations.IntroTextParser()

    def test_it_should_parse_intro_text_with_an_empty_suffix_and_a_tail(self):
        result = self.parser.parse('"A wager!"[] I returned.')
        (ensure(result)
         .equals([
             situations.Text('"A wager!"'),
             situations.Text('"A wager!" I returned.')
         ]))

    def test_it_should_parse_intro_text_with_a_suffix_and_a_tail(self):
        result = self.parser.parse('"Well then[."]," I said.')
        (ensure(result)
         .equals([
             situations.Text('"Well then."'),
             situations.Text('"Well then," I said.'),
         ]))

    def test_it_should_parse_intro_text_with_no_suffix_or_tail(self):
        result = self.parser.parse('"Well then."')
        (ensure(result)
         .equals([
             situations.Text('"Well then."'),
             situations.Text('"Well then."'),
         ]))

    def test_it_should_parse_intro_text_with_only_a_suffix(self):
        result = self.parser.parse('["Well then."]')
        (ensure(result)
         .equals([
             situations.Text('"Well then."'),
             situations.Text(''),
         ]))


class PlainTextParserTests(TestCase):
    def setUp(self):
        self.parser = situations.PlainTextParser()

    def test_it_should_parse_plain_text_without_features(self):
        result = self.parser.parse('Nothing to see here. Move along.')
        (ensure(result)
         .equals(situations.Text('Nothing to see here. Move along.')))

    def test_it_should_parse_plain_text_with_glue(self):
        result = self.parser.parse('Caught in a sticky web. <>')
        (ensure(result)
         .equals(situations.Text('Caught in a sticky web. ', sticky=True)))

    def test_it_should_parse_plain_text_with_a_predicate(self):
        result = self.parser.parse('{ foo == "bar" }Foo!')
        (ensure(result)
         .equals(situations.Text(
             'Foo!',
             sticky=False,
             predicate=Comparison('foo', '==', 'bar'))))

    def test_it_should_parse_plain_text_with_a_predicate_and_glue(self):
        result = self.parser.parse('{ foo == "bar" }Foo! <>')
        (ensure(result)
         .equals(situations.Text(
             'Foo! ',
             sticky=True,
             predicate=Comparison('foo', '==', 'bar'))))


class CompileSituationRulebookTests(TestCase):
    def test_it_should_compile_a_situation_rulebook(self):
        rulebook = yamlish.YamlParser().parse(TEST_RULEBOOK_YAMLISH).as_data()
        compiled = rules.compile_rulebook(rulebook)
        try:
            (ensure(compiled)
             .equals(EXPECTED_COMPILED_RULEBOOK))
        except EnsureError:
            pprint(DeepDiff(EXPECTED_COMPILED_RULEBOOK, compiled))
            raise

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
      - I found my box, lucky 1313.
""")


# EXPECTED_COMPILED_RULEBOOK = {
#     'Situation': [
#         rules.Rule(
#             name = 'intro',
#             predicates = [
#                 Predicate(
#                     name = 'Intro',
#                     predicate = Comparison(
#                         quality = 'Intro',
#                         comparison = '==',
#                         expression = 0,
#                     )
#                 ),
#             ],
#             baggage = situations.Situation(
#                 intro = [
#                     situations.Text(
#                         'It was raining steadily by the time I dropped my last rider '
#                         'off and swung by the post office on my way home.'
#                     ),
#                     situations.Text(
#                         'It was raining steadily by the time I dropped my last rider '
#                         'off and swung by the post office on my way home.'
#                     ),
#                 ],
#                 directives = [
#                     situations.Choice(
#                         intro = [
#                             situations.Text('The post office was closed.'),
#                             situations.Text('The post office was closed, '
#                                             'but I let myself in to the PO box room.')
#                         ],
#                         directives = [
#                             situations.Text(
#                                 'The fluorescent glare hurt my eyes after '
#                                 'the evening of headlight glare.'
#                             ),
#                         ]
#                     ),
#                     situations.Text('I found my box, lucky 1313.')
#                 ],
#             )
#         ),
#     ],
# }


EXPECTED_COMPILED_RULEBOOK = {
    'Situation': {
        'rules': [
            rules.Rule(
                name = 'intro',
                predicates = [
                    Predicate(
                        name = 'Intro',
                        predicate = Comparison(
                            quality = 'Intro',
                            comparison = '==',
                            expression = 0,
                        )
                    ),
                ],
            )
        ],
        'locations': {
            'intro': situations.Situation(
                intro = [
                    situations.Text(
                        'It was raining steadily by the time I dropped my last rider off...'
                    ),
                    situations.Text(
                        'It was raining steadily by the time I dropped my last rider '
                        'off and swung by the post office on my way home.'
                    ),
                ],
                directives = (
                    situations.Choice(location='intro::the-post-office-was-closed'),
                    situations.Text('I found my box, lucky 1313.'),
                ),
            ),
            'intro::the-post-office-was-closed': situations.Situation(
                intro = [
                    situations.Text(
                        'The post office was closed.'
                    ),
                    situations.Text(
                        'The post office was closed, but I let myself in to the PO box room.'
                    ),
                ],
                directives = (
                    situations.Text('The fluorescent glare hurt my eyes after the evening '
                                    'of headlight glare.'),
                ),
            ),
        },
    },
}
