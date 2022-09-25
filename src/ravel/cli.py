import logging

import click

from ravel.vm import runners


class Config:
    def __init__(self):
        pass


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option("--verbose", is_flag=True, default=False)
@click.option("--debug", is_flag=True, default=False)
@pass_config
def main(config, verbose, debug):
    config.verbose = verbose
    config.debug = debug
    if verbose or debug:
        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


@main.command()
@click.argument("directory", type=click.STRING)
@pass_config
def run(config, directory):
    """Run the indicated story."""
    runner = runners.ConsoleRunner(directory)
    runner.run()
