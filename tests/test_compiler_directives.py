from unittest import TestCase
from unittest.mock import Mock

from .helpers import ensure

from ravel import environments
from ravel import exceptions
from ravel import types
from ravel.compiler import directives


class CompileDirectiveTests(TestCase):
    def setUp(self):
        self.env = environments.Environment()

    def test_it_should_handle_text_directives(self):
        result = directives.compile_directive(self.env, 'Situation', Mock(), {'text': 'Hello world'})
        (ensure(result)
         .equals([
             (types.Text(text='Hello world'), {})
         ]))

    def test_it_should_handle_a_list_of_effects(self):
        effects = {
            'effect': ['foo = 1', 'bar = 2'],
        }
        result = directives.compile_directive(self.env, 'Situation', Mock(), effects)
        (ensure(result)
         .equals([
             (types.Operation(quality='foo', operator='=', expression=1), {}),
             (types.Operation(quality='bar', operator='=', expression=2), {})
         ]))

    def test_it_should_raise_parse_error_for_unknown_effect_type(self):
        effects = {
            'effect': {'wacky': 'effects'},
        }
        with self.assertRaises(exceptions.ParseError):
            directives.compile_directive(self.env, 'Situation', Mock(), effects)

    def test_it_should_raise_parse_error_for_unknown_directives(self):
        directive = {
            'foo': 'bar'
        }
        with self.assertRaises(exceptions.ParseError):
            directives.compile_directive(self.env, 'Situation', Mock(), directive)


class CompileChoiceTests(TestCase):
    def setUp(self):
        self.env = environments.Environment()

    def test_it_should_compile_a_choice_with_only_text(self):
        result = directives.compile_choice(self.env, 'Situation', 'parent', 'Hello, world!')
