from collections import namedtuple
import logging

from ravel import concepts
from ravel import predicates
from ravel.utils import strings

logger = logging.getLogger('situations')

Situation = namedtuple('Situation', ('intro', 'choices'))
Choice = namedtuple('Choice', ('intro', 'when', 'then', 'response'))


@concepts.handler('Situation')
def compile_situation_baggage(concept, rule_name, baggage):
    logger.debug('Compiling situation baggage for %s:%s:\n%r', concept, rule_name, baggage)
    intro, *choices = baggage
    if not isinstance(intro, str):
        raise TypeError("%s: First item in Situation baggage must be intro string." % rule_name)
    intro = compile_text(intro)
    choices = [compile_choice(concept, rule_name, ch) for ch in choices]
    return Situation(intro, choices)


def compile_choice(concept, parent_rule, choice):
    logger.debug('Compiling choice for %s:%s:\n%r', concept, parent_rule, choice)
    whens = ()
    thens = ()
    responses = []
    intro, *directives = choice['choice']
    if not isinstance(intro, str):
        raise TypeError("%s: First item in choice must be intro string." % parent_rule)
    intro = compile_text(intro)
    for directive in directives:
        if isinstance(directive, str):
            responses.append(strings.strip_outer_whitespace(directive))
        else:
            if 'when' in directive:
                whens = predicates.compile_ruleset(concept, parent_rule, directive['when'])
            elif 'then' in directive:
                thens = effects.compile_effects(concept, parent_rule, directive['then'])
            else:
                raise TypeError("%s: Unknown directive: %r" % (parent_rule, directive))
    response = compile_text('\n\n'.join(responses))
    return Choice(intro, whens, thens, response)


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

    template = text.get_template_from_string(util.strip_outer_whitespace(txt))

    def render_template(**context):
        return util.rewrap(template.render(**context))

    return render_template


def enact_consequences(choice, state):
    for consequence in choice.then:
        consequence(state)


def query_choices(queries, situation):
    queries = sorted(queries)
    for choice in situation.choices:
        if rules.query_predicates(queries, choice.when):
            yield choice
