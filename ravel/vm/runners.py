import functools
import logging
import sys
import textwrap

from .. import environments
from .. import loaders

from . import machines
from . import signals


def handle_exception(e):
    logging.exception('Something bad happened...')
    import ipdb
    ipdb.post_mortem()


def with_exception_handling(func):
    @functools.wraps(func)
    def run_with_exception_handling(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            handle_exception(e)

    return run_with_exception_handling


class ConsoleRunner:
    signals = signals.Signals()
    emit_text = print
    get_input = input

    @with_exception_handling
    def __init__(self, source_directory):
        self.env = environments.Environment(
            loader = loaders.FileSystemLoader(source_directory),
        )

        rulebook = self.env.load()
        self.vm = machines.VirtualMachine(
            **rulebook,
        )

        self.choices = {}

    def get_handlers(self):
        return [
            self.get_display_text_handler(self.vm),
            self.get_display_choice_handler(self.vm),
            self.get_wait_for_input_handler(self.vm),
        ]

    def get_display_text_handler(self, vm):
        @vm.signals.display_text.connect
        @with_exception_handling
        def display_text(vm, text, state):
            self.emit_text(textwrap.fill(text))

        return display_text

    def get_display_choice_handler(self, vm):
        @vm.signals.display_choice.connect
        @with_exception_handling
        def display_choice(vm, index, choice, text, state):
            self.choices[index] = choice
            self.emit_text('%s: %s' % (index, text))

        return display_choice

    def get_wait_for_input_handler(self, vm):
        @vm.signals.waiting_for_input.connect
        @with_exception_handling
        def wait_for_input(vm, send_input, state):
            choice = None
            while choice is None:
                chosen = self.get_input("What'll it be? ").lower()
                if chosen.isdigit():
                    try:
                        choice = self.choices[int(chosen)]
                    except (ValueError, KeyError):
                        self.emit_text("That's not an option.")
                        choice = None
                elif chosen == 's':
                    self.emit_text(repr(vm.qualities))
                elif chosen == 'q':
                    sys.exit(0)
                else:
                    self.emit_text("I'm sorry, what?")

            self.choices.clear()
            self.emit_text('\n')
            send_input(choice)

        return wait_for_input

    @with_exception_handling
    def run(self):
        try:
            handlers = self.get_handlers()  # noqa: F841
            self.vm.run()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            handle_exception(e)
            sys.exit(1)
