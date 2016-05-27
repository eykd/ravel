from collections import namedtuple
import logging

from parsimonious import Grammar

from ravel import concepts
from ravel import grammars
from ravel.parsers import BaseParser
from ravel.comparisons import ComparisonParser
from ravel import rules

logger = logging.getLogger('situations')

BaseSituation = namedtuple('Situation', ('intro', 'directives'))
Choice = namedtuple('Choice', ('intro', 'directives'))
BaseText = namedtuple('Text', ('text', 'sticky', 'predicate'))


class Situation(BaseSituation):
    __slots__ = ()

    def __new__(cls, intro, directives):
        return super().__new__(cls, intro, directives)


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

    intro, directives = compile_directives(concept, parent_rule, baggage)
    return Situation(intro, directives)


def compile_directives(concept, parent_rule, raw_directives):
    intro, *the_rest = raw_directives
    intro = IntroTextParser().parse(intro.text)
    directives = [compile_directive(concept, parent_rule, d) for d in the_rest]
    return intro, directives


def compile_directive(concept, parent_rule, raw_directive):
    if isinstance(raw_directive, dict):
        assert len(raw_directive) == 1, "Too many directives in %s" % raw_directive
        for key, directive in raw_directive.items():
            assert key.text == 'choice', "Unknown directive %s in %s" % (key.text, raw_directive)
            return compile_choice(concept, parent_rule, directive)

    else:
        return PlainTextParser().parse(raw_directive.text)


def compile_choice(concept, parent_rule, directives):
    logger.debug('Compiling choice for %s:%s:\n%r', concept, parent_rule, directives)
    intro, directives = compile_directives(concept, parent_rule, directives)
    return Choice(intro, directives)


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


def compile_text(txt):
    intro, *rest = txt.split('\n\n', 1)
    try:
        common_intro, remainder = intro.split('[', 1)
        short_intro, long_intro = remainder.split(']', 1)
    except ValueError:
        common_intro = intro
        short_intro = long_intro = ''

    if short_intro or long_intro:
        txt = '%(common)s{%% if short %%}%(short)s{%% else %%}%(long)s%(rest)s{%% endif %%}' % {
            'common': common_intro,
            'short': short_intro,
            'long': long_intro,
            'rest': ('\n\n' + '\n\n'.join(rest)) if rest else '',
        }
    for search, replace in tag_replace:
        txt = txt.replace(search, replace)

#     template = text.get_template_from_string(util.strip_outer_whitespace(txt))
#     def render_template(**context):
#         return util.rewrap(template.render(**context))

#     return render_template


def enact_consequences(choice, state):
    for consequence in choice.then:
        consequence(state)


def query_choices(queries, situation):
    queries = sorted(queries)
    for choice in situation.choices:
        if rules.query_predicates(queries, choice.when):
            yield choice
