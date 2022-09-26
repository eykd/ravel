import functools
import logging
import pdb
import sys
import textwrap
from typing import Callable

from attrs import define
from colorclass import Color

from .. import environments, loaders
from . import machines, signals
from .states import State


@define(auto_attrib=True, frozen=True)
class DisplayText:
    text: str
    state: dict
    sticky: bool


@define(auto_attrib=True, frozen=True)
class DisplayChoice:
    index: int
    choice: str
    text: str
    state: dict


@define(auto_attrib=True, frozen=True)
class Waiter:
    send_input: Callable
    state: State


def handle_exception(debug=False):
    logging.exception("Something bad happened...")
    if debug:
        pdb.post_mortem()
    sys.exit(1)


def with_exception_handling(debug):
    def wrapper(func):
        @functools.wraps(func)
        def run_with_exception_handling(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception:
                handle_exception(debug)

        return run_with_exception_handling

    return wrapper


class StatefulRunner:
    def __init__(self, env):
        self.env = env
        rulebook = self.env.load()
        self.vm = machines.VirtualMachine(**rulebook)

        self.choices = []
        self.out_queue = []

        self.waiting_for_choice = False
        self.waiter = None

    def enqueue_text(self, text):
        self.out_queue.append(text)

    def clear_text_queue(self):
        self.out_queue[:] = ()

    def consume_text_queue(self):
        yield from iter(self.out_queue)
        self.clear_text_queue()

    def get_display_text_handler(self, vm):
        @vm.signals.display_text.connect
        def display_text(vm, text, state, sticky=False):
            self.out_queue.append(DisplayText(text=text, state=state, sticky=sticky))

        return display_text

    def get_display_choice_handler(self, vm):
        @vm.signals.display_choice.connect
        def display_choice(vm, index, choice, text, state):
            self.choices.append(DisplayChoice(index=index, choice=choice, text=text, state=state))

        return display_choice

    def get_wait_for_input_handler(self, vm):
        @vm.signals.waiting_for_input.connect
        def wait_for_input(vm, send_input, state):
            self.waiting_for_choice = True
            self.waiter = Waiter(send_input=send_input, state=state)

        return wait_for_input

    def choose(self, choice_idx: int):
        if not self.waiting_for_choice:
            raise RuntimeError("VM is not currently waiting for a choice.")

        choice = self.choices[choice_idx]
        waiter = self.waiter

        self.choices[:] = ()
        self.waiter = None
        self.waiting_for_choice = False

        waiter.send_input(choice)


class ConsoleRunner:
    signals = signals.Signals()

    def __init__(self, source_directory, debug=False):
        self.debug = debug
        try:
            self.env = environments.Environment(
                loader=loaders.FileSystemLoader(source_directory),
            )

            rulebook = self.env.load()
            self.vm = machines.VirtualMachine(
                **rulebook,
            )
        except Exception:
            handle_exception(debug)

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
        @with_exception_handling(self.debug)
        def display_text(vm, text, state, sticky=False):
            text = "{yellow}%s{/yellow}" % textwrap.fill(text)
            if not sticky:
                text += "\n"
            self.emit_text(text, sticky=sticky)

        return display_text

    def get_display_choice_handler(self, vm):
        @vm.signals.display_choice.connect
        @with_exception_handling(self.debug)
        def display_choice(vm, index, choice, text, state):
            self.choices.append(choice)
            self.emit_text(f"{{green}}{len(self.choices)}{{/green}}: {{yellow}}{text}{{/yellow}}")

        return display_choice

    def get_wait_for_input_handler(self, vm):
        @vm.signals.waiting_for_input.connect
        @with_exception_handling(self.debug)
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

    def run(self):
        try:
            handlers = self.get_handlers()  # noqa: F841
            self.vm.run()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            handle_exception(e)
            sys.exit(1)
