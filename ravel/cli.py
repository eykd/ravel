import logging
import sys

import click

from ravel import rules
from ravel import queries
from ravel import yamlish
from ravel.concepts import situations


class Config:
    def __init__(self):
        pass


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option('--verbose', is_flag=True, default=False)
@pass_config
def main(config, verbose):
    config.verbose = verbose


@main.command()
@click.argument('story', type=click.File('r'))
@pass_config
def run(config, story):
    """Run the indicated storyfile.
    """
    import ipdb; ipdb.set_trace()
    state = {}
    try:
        rulebook = rules.compile_rulebook(yamlish.parse(story.read()).as_data())
    except:
        logging.exception('Something bad happened while compiling the rulebook...')
        import ipdb
        ipdb.post_mortem()
        sys.exit(1)
    else:
        situation = queries.query_top('Situation', state, rulebook)
        _display_situation(state, situation, rulebook)


def _display_situation(state, situation, rulebook):
    choices = []
    for directive in situation.directives:
        if isinstance(directive, situations.Text):
            click.echo(directive.text)
        elif isinstance(directive, situations.Choice):
            target = queries.query_by_name(directive.location, rulebook['Situation'])
            choices.append(target)
            click.echo('%s: %s' % (len(choices), target.intro.text))
        elif isinstance(directive, situations.GetChoice):
            while True:
                click.echo('? ', nl=False)
                c = click.getchar()
                click.echo(c)
                try:
                    choice = int(c) - 1
                except ValueError:
                    if c.lower() == 'q':
                        sys.exit()
                    pass
                else:
                    if 0 <= choice < len(choices):
                        click.echo()
                        _display_situation(state, choices[choice], rulebook)
                        break
