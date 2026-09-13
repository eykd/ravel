"""Guard against unescaped backslashes creeping back into the PEG sources.

The grammar text lives in raw strings, so a single-backslash ``\\s`` reaches
parsimonious verbatim. Parsimonious then ``literal_eval``s the token text and
Python emits ``SyntaxWarning: invalid escape sequence`` -- a SyntaxError in a
future Python. Rebuilding each grammar under an error filter re-triggers that
``literal_eval``, so a regressed backslash fails here.

A global ``filterwarnings = ["error::SyntaxWarning"]`` cannot do this job: syml
builds its own grammar at import time, and both warnings are attributed to
``<unknown>:1`` (the ``literal_eval`` frame), so there is no module to scope an
ignore to.
"""

import warnings

import parsimonious.grammar
import pytest

from ravel import grammars

GRAMMAR_NAMES = [
    "base_expression_grammar",
    "operation_grammar",
    "comparison_grammar",
    "intro_text_grammar",
    "plain_text_grammar",
]


class TestGrammars:
    @pytest.mark.parametrize("name", GRAMMAR_NAMES)
    def test_it_builds_without_syntax_warnings(self, name):
        grammar_string = getattr(grammars, name)
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            parsimonious.grammar.Grammar(grammar_string)
