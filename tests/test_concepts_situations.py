from unittest import TestCase

from pprint import pprint
import textwrap

import ensure
from ensure import EnsureError
from deepdiff import DeepDiff

from ravel.comparisons import Comparison
from ravel import exceptions
from ravel.predicates import Predicate
from ravel import rules
from ravel import yamlish
from ravel.concepts import situations

ensure.unittest_case.maxDiff = None
ensure = ensure.ensure


class TextTests(TestCase):
    def test_it_should_present_a_helpful_repr_for_plain_text(self):
        text = situations.Text('Some plain text.')
        (ensure(repr(text))
         .equals("<Text: 'Some plain text.'>"))

    def test_it_should_present_a_helpful_repr_for_sticky_text(self):
        text = situations.Text('Some plain text.', sticky=True)
        (ensure(repr(text))
         .equals("<Text (sticky): 'Some plain text.'>"))

    def test_it_should_present_a_helpful_repr_for_plain_text_with_predicate(self):
        predicate = Predicate(
            name = 'Intro',
            predicate = Comparison(
                quality = 'Intro',
                comparison = '==',
                expression = 0,
            )
        )

        text = situations.Text('Some plain text.', predicate=predicate)
        (ensure(repr(text))
         .equals("<Text {Intro: ('Intro' == 0)}: 'Some plain text.'>"))

    def test_it_should_stringify_nicely(self):
        text = situations.Text('Some plain text.')
        ensure(str(text)).equals('Some plain text.')


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

    def test_it_should_fail_to_compile_an_unknown_directive(self):
        bad_rulebook_yamlish = yamlish.YamlParser().parse(textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - foo: bar
        """)).as_data()
        (ensure(rules.compile_rulebook)
         .called_with(bad_rulebook_yamlish)
         .raises(exceptions.ParseError))

    def test_it_should_fail_to_compile_a_multipronged_directive(self):
        bad_rulebook_yamlish = yamlish.YamlParser().parse(textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - Some intro text.
              - choice:
                  - foo
                  - bar
                text: This shouldn't be!
        """)).as_data()
        (ensure(rules.compile_rulebook)
         .called_with(bad_rulebook_yamlish)
         .raises(exceptions.ParseError))

    def test_it_should_fail_to_compile_with_missing_intro_text(self):
        bad_rulebook_yamlish = yamlish.YamlParser().parse(textwrap.dedent("""
            intro:
              - Situation
              - when:
                - Intro == 0

              - foo: bar
        """)).as_data()
        (ensure(rules.compile_rulebook)
         .called_with(bad_rulebook_yamlish)
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
          - choice: I quietly cursed the light, wishing for the dark.
          - choice:
            - I quietly gave thanks for the light.
      - I found my box, lucky 1313.
      - text: What a lovely number.
""")


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
                intro = situations.Text(
                    'It was raining steadily by the time I dropped my last rider off...'
                ),
                directives = [
                    situations.Text(
                        'It was raining steadily by the time I dropped my last rider '
                        'off and swung by the post office on my way home.'
                    ),
                    situations.Choice(location='intro::the-post-office-was-closed'),
                    situations.GetChoice(),
                    situations.Text('I found my box, lucky 1313.'),
                    situations.Text('What a lovely number.'),
                ],
            ),
            'intro::the-post-office-was-closed': situations.Situation(
                intro = situations.Text(
                    'The post office was closed.'
                ),
                directives = [
                    situations.Text(
                        'The post office was closed, but I let myself in to the PO box room.'
                    ),
                    situations.Text('The fluorescent glare hurt my eyes after the evening '
                                    'of headlight glare.'),
                    situations.Choice(location='intro::i-quietly-cursed-the-light-wishing-for-the-dark'),
                    situations.Choice(location='intro::i-quietly-gave-thanks-for-the-light'),
                    situations.GetChoice(),
                ],
            ),
            'intro::i-quietly-cursed-the-light-wishing-for-the-dark': situations.Situation(
                intro = situations.Text(
                    'I quietly cursed the light, wishing for the dark.'
                ),
                directives = [
                    situations.Text(
                        'I quietly cursed the light, wishing for the dark.'
                    ),
                ],
            ),
            'intro::i-quietly-gave-thanks-for-the-light': situations.Situation(
                intro = situations.Text(
                    'I quietly gave thanks for the light.'
                ),
                directives = [
                    situations.Text(
                        'I quietly gave thanks for the light.'
                    ),
                ],
            ),
        },
    },
}
