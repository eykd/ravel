from collections import defaultdict
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from ..environments import Environment
from . import machines
from .signals import SIGNAL, signal

if TYPE_CHECKING:
    from ravel.events import waiting_for_input
    from ravel.types import Choice


class StatefulRunner:
    def __init__(self, environment: Environment):
        self.environment = environment
        self.vm = machines.VirtualMachine(**self.environment.load())

        self.running = False
        self.waiting_for_choice = False
        self.waiter: Optional[waiting_for_input] = None
        self.choice_events: List[Choice] = []

        self._handlers: Dict[str, List[Callable]] = defaultdict(list)

    def __enter__(self):
        self.running = True
        self._setup_handlers()
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

    def connect(self, enum: SIGNAL, handler):
        signal(enum.value).connect(handler)
        self._handlers[enum.value].append(handler)

    def _setup_handlers(self):
        self.connect(SIGNAL.display_text, self.handle_display_text)
        self.connect(SIGNAL.display_choice, self.handle_display_choice)
        self.connect(SIGNAL.waiting_for_input, self.handle_waiting_for_input)
        for enum in SIGNAL:
            self.connect(enum, self.handle_any_event)

    def setup_handlers(self):
        pass

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
