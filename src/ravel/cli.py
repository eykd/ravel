# pragma: nocover
import logging
import pdb
import sys
import textwrap

import click
from colorclass import Color

from ravel import loaders
from ravel.environments import Environment
from ravel.vm import runners
from ravel.vm.signals import SIGNAL


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
    env = Environment(
        loader=loaders.FileSystemLoader(directory),
    )
    with ConsoleRunner(env, debug=config.debug, verbose=config.verbose) as runner:
        runner.run()


class ConsoleRunner(runners.StatefulRunner):
    def __init__(self, env: Environment, debug: bool = False, verbose: bool = False):
        super().__init__(env)
        self.debug = debug
        self.verbose = verbose
        self.choice_events = []

    def get_input(self, text):
        return input(Color(text))

    def handle_display_text(self, event):
        print(Color("{yellow}%s{/yellow}\n" % textwrap.fill(event.text)))

    def handle_display_choice(self, event):
        self.choice_events.append(event.choice)
        print(Color(f"{{green}}{len(self.choice_events)}{{/green}}: {{yellow}}{event.text}{{/yellow}}"))

    def handle_waiting_for_input(self, event):
        choice = None
        while choice is None:
            print()
            chosen = self.get_input("{green}What'll it be?{/green} ").lower()
            if chosen.isdigit():
                try:
                    choice = self.choice_events[int(chosen) - 1]
                except (ValueError, IndexError):
                    print(Color("{red}That's not an option.{/red}"))
                    choice = None
            elif chosen == "s":
                print(repr(self.vm.qualities))
            elif chosen == "q":
                sys.exit(0)
            else:
                print(Color("{red}I'm sorry, what?{/red}"))

        self.choice_events[:] = ()
        print()
        print(Color("{cyan}%s{/cyan}" % ("-" * 80)))
        event.send_input(choice)

    def setup_handlers(self):
        self.connect(SIGNAL.quality_changed, self.handle_quality_changed)
        self.connect(SIGNAL.enter_state, self.handle_enter_state)
        self.connect(SIGNAL.exit_state, self.handle_exit_state)
        self.connect(SIGNAL.pause_state, self.handle_pause_state)
        self.connect(SIGNAL.resume_state, self.handle_resume_state)

    def handle_quality_changed(self, event):
        if self.verbose:
            print(
                Color(
                    f"## {{red}}{event.quality}{{/red}}"
                    f" was {{yellow}}{event.initial_value}{{/yellow}},"
                    f" now {{green}}{event.new_value}{{/green}}"
                )
            )

    def handle_enter_state(self, event):
        if self.verbose:
            print(Color(f"## {{green}}Entering{{/green}} {event.state.__class__.__name__}"))

    def handle_exit_state(self, event):
        if self.verbose:
            print(Color(f"## {{red}}Exiting{{/red}} {event.state.__class__.__name__}"))

    def handle_pause_state(self, event):
        if self.verbose:
            print(Color(f"## {{yellow}}Pausing{{/yellow}} {event.state.__class__.__name__}"))

    def handle_resume_state(self, event):
        if self.verbose:
            print(Color(f"## {{green}}Resuming{{/green}} {event.state.__class__.__name__}"))

    def handle_exception(self, debug=False):
        logging.exception("Something bad happened...")
        if debug:
            pdb.post_mortem()
        sys.exit(1)

    def run(self):
        try:
            while True:
                self.vm.run()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)
        except Exception as e:
            self.handle_exception(e)
            sys.exit(1)
