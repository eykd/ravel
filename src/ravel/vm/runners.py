import functools
import logging
import pdb
import sys
import textwrap
from collections import defaultdict

from colorclass import Color

from .. import loaders
from ..environments import Environment
from . import machines
from .signals import SIGNAL, signal


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
    def __init__(self, env: Environment):
        self.env = env
        self.vm = machines.VirtualMachine(**self.env.load())

        self.choice_events = []
        self.text_events = []
        self.all_events = []

        self.running = False
        self.waiting_for_choice = False
        self.waiter = None

        self._handlers = defaultdict(list)

    def __enter__(self):
        self.running = True
        self.setup_handlers()
        self.begin()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.teardown_handlers()
        self.running = False

    def __iter__(self):
        while True:
            try:
                self.vm.do_next_in_queue()
            except IndexError:
                break
            else:
                yield from self.consume_event_queue()

    def _connect(self, enum: SIGNAL, handler):
        signal(enum.value).connect(handler)
        self._handlers[enum.value].append(handler)

    def setup_handlers(self):
        self._connect(SIGNAL.display_text, self._handle_display_text)
        self._connect(SIGNAL.display_choice, self._handle_display_choice)
        self._connect(SIGNAL.waiting_for_input, self._handle_wait_for_input)
        for enum in SIGNAL:
            self._connect(enum, self._handle_event)

    def _handle_event(self, event):
        self.all_events.append(event)

    def _handle_display_text(self, event):
        self.text_events.append(event)

    def _handle_display_choice(self, event):
        self.choice_events.append(event)

    def _handle_wait_for_input(self, event):
        self.waiting_for_choice = True
        self.waiter = event

    def teardown_handlers(self):
        for signame, handlers in self._handlers.items():
            for handler in handlers:
                signal(signame).disconnect(handler)
        self._handlers.clear()

    def begin(self):
        self.vm.begin()

    def clear_text_queue(self):
        self.text_events[:] = ()

    def consume_text_queue(self):
        yield from iter(self.text_events)
        self.clear_text_queue()

    def clear_event_queue(self):
        self.all_events[:] = ()

    def consume_event_queue(self):
        yield from iter(self.all_events)
        self.clear_event_queue()

    def choose(self, choice_idx: int):
        if not self.waiting_for_choice:
            raise RuntimeError("VM is not currently waiting for a choice.")

        choice = self.choice_events[choice_idx]
        waiter = self.waiter

        self.choice_events[:] = ()
        self.waiter = None
        self.waiting_for_choice = False

        waiter.send_input(choice.choice)


class ConsoleRunner:
    def __init__(self, source_directory, debug=False):
        self.debug = debug
        try:
            self.env = Environment(
                loader=loaders.FileSystemLoader(source_directory),
            )

            rulebook = self.env.load()
            self.vm = machines.VirtualMachine(
                **rulebook,
            )
        except Exception:
            handle_exception(debug)

        self.choice_events = []

        self.text_events = []

    def enqueue_text(self, text):
        self.text_events.append(text)

    def get_enqueued_text(self):
        text = "".join(self.text_events)
        self.text_events[:] = ()
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
        def display_text(event):
            text = "{yellow}%s{/yellow}" % textwrap.fill(event.text)
            if not event.sticky:
                text += "\n"
            self.emit_text(text, sticky=event.sticky)

        return display_text

    def get_display_choice_handler(self, vm):
        @vm.signals.display_choice.connect
        @with_exception_handling(self.debug)
        def display_choice(event):
            self.choice_events.append(event.choice)
            self.emit_text(f"{{green}}{len(self.choice_events)}{{/green}}: {{yellow}}{event.text}{{/yellow}}")

        return display_choice

    def get_wait_for_input_handler(self, vm):
        @vm.signals.waiting_for_input.connect
        @with_exception_handling(self.debug)
        def wait_for_input(event):
            choice = None
            while choice is None:
                self.emit_text("")
                chosen = self.get_input("{green}What'll it be?{/green} ").lower()
                if chosen.isdigit():
                    try:
                        choice = self.choice_events[int(chosen) - 1]
                    except (ValueError, IndexError):
                        self.emit_text("{red}That's not an option.{/red}")
                        choice = None
                elif chosen == "s":
                    self.emit_text(repr(vm.qualities))
                elif chosen == "q":
                    sys.exit(0)
                else:
                    self.emit_text("{red}I'm sorry, what?{/red}")

            self.choice_events[:] = ()
            self.emit_text("")
            self.emit_text("{cyan}%s{/cyan}" % ("-" * 80))
            event.send_input(choice)

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
