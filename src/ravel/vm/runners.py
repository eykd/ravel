import functools
import logging
import sys
import textwrap

from colorclass import Color

from .. import environments
from .. import loaders

from . import machines
from . import signals


def handle_exception(e):
    logging.exception("Something bad happened...")
    import pdb

    pdb.post_mortem()


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

    @with_exception_handling
    def __init__(self, source_directory):
        self.env = environments.Environment(
            loader=loaders.FileSystemLoader(source_directory),
        )

        rulebook = self.env.load()
        self.vm = machines.VirtualMachine(
            **rulebook,
        )

        self.choices = []

        self.out_queue = []

    def enqueue_text(self, text):
        self.out_queue.append(text)

    def get_enqueued_text(self):
        text = "".join(self.out_queue)
        self.out_queue[:] = ()
        return Color(text)

    def emit_text(self, text, sticky=False):
        logging.info(f"Emitting text (sticky={sticky}): {text!r}")
        self.enqueue_text(text)
        if not sticky:
            print(self.get_enqueued_text())

    def get_input(self, text):
        self.enqueue_text(text)
        return input(self.get_enqueued_text())

    def get_handlers(self):
        return [
            self.get_display_text_handler(self.vm),
            self.get_display_choice_handler(self.vm),
            self.get_wait_for_input_handler(self.vm),
        ]

    def get_display_text_handler(self, vm):
        @vm.signals.display_text.connect
        @with_exception_handling
        def display_text(vm, text, state, sticky=False):
            text = "{yellow}%s{/yellow}" % textwrap.fill(text)
            if not sticky:
                text += "\n"
            self.emit_text(text, sticky=sticky)

        return display_text

    def get_display_choice_handler(self, vm):
        @vm.signals.display_choice.connect
        @with_exception_handling
        def display_choice(vm, index, choice, text, state):
            self.choices.append(choice)
            self.emit_text(
                f"{{green}}{len(self.choices)}{{/green}}: {{yellow}}{text}{{/yellow}}"
            )

        return display_choice

    def get_wait_for_input_handler(self, vm):
        @vm.signals.waiting_for_input.connect
        @with_exception_handling
        def wait_for_input(vm, send_input, state):
            choice = None
            while choice is None:
                self.emit_text("")
                chosen = self.get_input("{green}What'll it be?{/green} ").lower()
                if chosen.isdigit():
                    try:
                        choice = self.choices[int(chosen) - 1]
                    except (ValueError, IndexError):
                        self.emit_text("{red}That's not an option.{/red}")
                        choice = None
                elif chosen == "s":
                    self.emit_text(repr(vm.qualities))
                elif chosen == "q":
                    sys.exit(0)
                else:
                    self.emit_text("{red}I'm sorry, what?{/red}")

            self.choices[:] = ()
            self.emit_text("")
            self.emit_text("{cyan}%s{/cyan}" % ("-" * 80))
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
