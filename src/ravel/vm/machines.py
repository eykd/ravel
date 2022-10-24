from __future__ import annotations

import logging
from collections import deque
from functools import partial
from typing import TYPE_CHECKING, Callable, Deque, Dict, Optional

from attrs import define, field
from funcy import first

from ravel import queries, types
from ravel.vm import events
from ravel.vm.signals import Signals
from ravel.vm.states import Begin, State

if TYPE_CHECKING:  # pragma: nocover
    from ravel.types import Operation

logger = logging.getLogger("ravel.vm")


@define
class VirtualMachine:
    """The VirtualMachine is a stack of State objects. Each State controls the
    transitions that it may make. Some states will simply pop themselves off
    the stack, reverting control to the state underneath.

    So, we first need an initial state; that's a display-possible-situations
    state. Display the possible situations available based on the current set
    of qualities. The only transition trigger is to pick a situation, and push
    it with a display-situation state onto the stack, entering the
    display-situation state.

    When we enter the display-situation state, we iterate through the items in
    its situation, starting from the current index (default 0), emitting
    display events as we go, until we encounter a GetChoices or the end of the
    Situation.

    In the display-situation state, if we encounter a GetChoices state, we push
    a getting-choices state onto the stack.

    In the display-situation state, if we encounter the end of the Situation,
    we pop the state off the stack.

    In the getting-choices state, when a choice is chosen, we push a new
    display-situation state onto the stack.

    """

    rulebook: types.Rulebook = field()
    qualities: Dict = field(factory=dict)
    stack: Deque[State] = field(factory=deque)
    signals: Signals = field(factory=Signals)
    begin_state: Begin = field(default=Begin)
    queue: Deque[Callable] = field(factory=deque)

    def enqueue(self, callable_action: Callable, *args, **kwargs):
        logger.debug(f"Enqueuing action {callable_action.__name__}: {args!r}, {kwargs!r}")
        self.queue.append(partial(callable_action, *args, **kwargs))

    def do_next_in_queue(self):
        logger.debug(f"Doing next: {first(self.queue)}")
        self.queue.popleft()()

    def begin(self):
        logger.debug("Beginning...")
        self.enqueue(self.initialize_from_givens)
        self.enqueue(self.push, self.begin_state())

    def run(self):  # pragma: nocover
        self.begin()
        while self.queue:
            self.do_next_in_queue()

    def apply_operation(self, op: Operation):
        logger.debug("Applying operation: %r", op)
        quality = op.quality
        initial_value = self.qualities.get(quality)
        new_value = op.evaluate(initial_value, qualities=self.qualities)
        self.qualities[quality] = new_value
        logger.debug(f"Quality [{quality}] was {initial_value!r}, now {new_value!r}")
        self.send(
            events.quality_changed(
                quality=quality,
                initial_value=initial_value,
                new_value=new_value,
            )
        )

    def initialize_from_givens(self):
        logger.debug(f"Initializing from givens: {self.rulebook.givens!r}")
        state = self.qualities
        for op in self.rulebook.givens:
            self.apply_operation(op)
        self.qualities = state

    @property
    def top_state(self) -> Optional[State]:
        return self.stack[-1] if self.stack else None

    def push(self, state: State):
        logger.debug(f"Pushing state: {state!r}")
        self.enqueue(self.do_push, state)

    def do_push(self, state):
        top_state = self.top_state
        if top_state is not None:
            logger.debug(f"Pausing state {top_state!r}")
            top_state.pause(self)
            self.send(events.pause_state(state=top_state))

        logger.debug(f"Entering state {state!r}")
        self.stack.append(state)
        state.enter(self)
        self.send(events.enter_state(state=state))

    def pop(self):
        logger.debug("Popping state")
        self.enqueue(self.do_pop)

    def do_pop(self):
        state = self.stack.pop()
        logger.debug(f"Exiting state {state!r}")
        state.exit(self)
        self.send(events.exit_state(state=state))

        top_state = self.top_state
        if top_state is not None:
            logger.debug(f"Resuming state {top_state!r}")
            top_state.resume(self)
            self.send(events.resume_state(state=top_state))

    def send(self, event):
        logger.debug(f"Sending signal {event.name!r}")
        signal = getattr(self.signals, event.name)
        signal.send(event)

    def get_situation(self, name):
        logger.debug("Getting situation %s", name)
        return queries.query_by_name(self.rulebook, "Situation", name)
