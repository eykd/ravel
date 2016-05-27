import click

from ravel import rules
from ravel import queries
from ravel import yamlish


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
    state = {}
    rulebook = rules.compile_rulebook(yamlish.parse(story.read()).as_data())
    situation = queries.query_top('Situation', state, rulebook)
    click.echo(situation.intro.head.text + situation.intro.suffix.text)
