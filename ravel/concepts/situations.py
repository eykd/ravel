from collections import namedtuple
import itertools as it
import logging

from parsimonious import Grammar
from slugify import slugify_unicode

from ravel import concepts
from ravel import exceptions
from ravel import grammars
from ravel.parsers import BaseParser
from ravel.comparisons import ComparisonParser
from ravel.utils.data import merge_dicts

logger = logging.getLogger('situations')

BaseSituation = namedtuple('Situation', ('intro', 'directives'))
Choice = namedtuple('Choice', ('location'))
BaseText = namedtuple('Text', ('text', 'sticky', 'predicate'))


class Situation(BaseSituation):
    __slots__ = ()

    def __new__(cls, intro, directives):
        return super().__new__(cls, intro, directives)


class GetChoice(namedtuple('GetChoice', ())):
    __slots__ = ()


class Text(BaseText):
    __slots__ = ()

    def __new__(cls, text, sticky=False, predicate=None):
        return super().__new__(cls, text, sticky, predicate)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.text == other.text
            and self.sticky == other.sticky
        )

    def __repr__(self):
        kind = self.__class__.__name__
        if self.sticky:
            kind += ' (sticky)'
        if self.predicate:
            kind += (' ' + repr(self.predicate))

        return '<%s: %r>' % (kind, self.text)

    def __str__(self):
        return self.text


class IntroTextParser(BaseParser):
    grammar = Grammar(grammars.intro_text_grammar)

    def visit_head(self, node, children):
        return node.text

    def visit_suffix(self, node, children):
        return node.text.strip('[]')

    def visit_tail(self, node, children):
        return node.text

    def visit_intro(self, node, children):
        head, rest = children
        if rest is not None:
            suffix, tail = rest
        else:
            suffix = tail = ''

        return [
            Text(head + suffix),
            Text(head + tail),
        ]


class PlainTextParser(ComparisonParser):
    grammar = Grammar(grammars.plain_text_grammar)

    def visit_text(self, node, children):
        return node.text

    def visit_glue(self, node, children):
        return True

    def visit_line(self, node, children):
        predicate, text, *sticky = children
        sticky = self.reduce_children(sticky)
        result = Text(text, sticky=bool(sticky), predicate=predicate)
        return result


@concepts.handler('Situation')
def compile_situation_baggage(concept, parent_rule, baggage):
    logger.debug('Compiling situation baggage for %s:%s:\n%r', concept, parent_rule, baggage)

    intro, directives, subsituations = compile_directives(concept, parent_rule, baggage)
    return {
        parent_rule: Situation(intro, directives),
        **merge_dicts(*subsituations),
    }


def compile_directives(concept, parent_rule, raw_directives):
    intro, *the_rest = raw_directives
    try:
        intro, first_text = IntroTextParser().parse(intro.text)
    except AttributeError:
        raise exceptions.ParseError("No intro text found:\n%r" % intro)
    directives = []
    subsituations = []
    if the_rest:
        last_directive = None
        for item in the_rest:
            directive, situations = compile_directive(concept, parent_rule, item)
            if isinstance(last_directive, Choice) and not isinstance(directive, Choice):
                directives.append(GetChoice())
            directives.append(directive)
            subsituations.append(situations)
            last_directive = directive
        if isinstance(last_directive, Choice):
            directives.append(GetChoice())
    return intro, list(it.chain([first_text], directives)), subsituations


def compile_directive(concept, parent_rule, raw_directive):
    if isinstance(raw_directive, dict):
        if len(raw_directive) != 1:
            raise exceptions.ParseError("Too many directives in %s" % raw_directive)
        key, directive = list(raw_directive.items())[0]
        if key.text == 'choice':
            return compile_choice(concept, parent_rule, directive)
        elif key.text == 'text':
            return compile_text(concept, parent_rule, directive)
        else:
            raise exceptions.ParseError("Unknown directive %s in %r" % (key.text, raw_directive))
    else:
        return compile_text(concept, parent_rule, raw_directive)


def compile_text(concept, parent_rule, raw_directive):
    return PlainTextParser().parse(raw_directive.text), {}


def compile_choice(concept, parent_rule, directives):
    logger.debug('Compiling choice for %s:%s:\n%r', concept, parent_rule, directives)
    if not isinstance(directives, list):
        directives = [directives]
    intro, directives, subsituations = compile_directives(concept, parent_rule, directives)
    subrule = '%s::%s' % (parent_rule, slugify_unicode(intro.text, to_lower=True))
    return (
        Choice(subrule),
        {subrule: Situation(intro, directives), **merge_dicts(*subsituations)}
    )


tag_replace = [
    ('{/?}', '{% endif %}'),
    ('{-/?}', '{%- endif %}'),
    ('{/?-}', '{% endif %}'),
    ('{??}', '{% else %}'),
    ('{??', '{% elif'),
    ('{-??', '{%- elif'),
    ('{?', '{% if'),
    ('{-?', '{%- if'),
    ('?-}', '-%}'),
    ('?}', '%}'),
]


