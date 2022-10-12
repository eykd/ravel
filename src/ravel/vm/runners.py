import functools
import logging
import pdb
import sys
import textwrap
from collections import defaultdict

from colorclass import Color

from ..environments import Environment
from . import machines
from .signals import SIGNAL, signal


def handle_exception(debug=False):  # pragma: nocover
    logging.exception("Something bad happened...")
    if debug:
        pdb.post_mortem()
    sys.exit(1)


def with_exception_handling(debug):  # pragma: nocover
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

        self.running = False
        self.waiting_for_choice = False
        self.waiter = None

        self._handlers = defaultdict(list)

    def __enter__(self):
        self.running = True
        self.setup_handlers()
        self.begin()
        return self

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
        self._connect(SIGNAL.display_text, self.handle_display_text)
        self._connect(SIGNAL.display_choice, self.handle_display_choice)
        self._connect(SIGNAL.waiting_for_input, self.handle_waiting_for_input)
        for enum in SIGNAL:
            self._connect(enum, self.handle_any_event)

    def handle_any_event(self, event):
        pass

    def handle_display_text(self, event):
        pass

    def handle_display_choice(self, event):
        pass

    def handle_waiting_for_input(self, event):
        pass

    def teardown_handlers(self):
        for signame, handlers in self._handlers.items():
            for handler in handlers:
                signal(signame).disconnect(handler)
        self._handlers.clear()

    def begin(self):
        self.vm.begin()

    def clear_text_events(self):
        self.text_events[:] = ()

    def consume_text_events(self):
        yield from iter(self.text_events)
        self.clear_text_events()

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


class QueueRunner(StatefulRunner):
    def __init__(self, env: Environment):
        super().__init__(env)
        self.choice_events = []
        self.text_events = []
        self.all_events = []

    def handle_any_event(self, event):
        self.all_events.append(event)

    def handle_display_text(self, event):
        self.text_events.append(event)

    def handle_display_choice(self, event):
        self.choice_events.append(event)

    def handle_waiting_for_input(self, event):
        self.waiting_for_choice = True
        self.waiter = event


class ConsoleRunner(StatefulRunner):
    def __init__(self, env: Environment, debug: bool = False):
        super().__init__(env)
        self.debug = debug
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

    def run(self):
        try:
            while True:
                self.vm.run()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            handle_exception(e)
            sys.exit(1)
