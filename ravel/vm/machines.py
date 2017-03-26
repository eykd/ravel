from collections import deque
from functools import partial
import logging

import attr

from .. import queries

from . import signals
from . import states


logger = logging.getLogger('ravel.vm')


@attr.s
class VirtualMachine:
    """The VirtualMachine is a stack of State objects. Each State controls the
    transitions that it may make. Some states will simply pop themselves off
    the stack, reverting control the the state underneath.

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
    rulebook = attr.ib()
    givens = attr.ib(default=attr.Factory(list))
    metadata = attr.ib(default=attr.Factory(dict))
    qualities = attr.ib(default=attr.Factory(dict))
    stack = attr.ib(default=attr.Factory(deque))
    signals = attr.ib(default=attr.Factory(signals.Signals))
    begin_state = attr.ib(default=states.Begin)
    queue = attr.ib(default=attr.Factory(deque))

    def enqueue(self, callable_action, *args, **kwargs):
        logger.debug('Enqueuing action %r: %r, %r', callable_action, args, kwargs)
        self.queue.append(partial(callable_action, *args, **kwargs))

    def do_next_in_queue(self):
        self.queue.popleft()()

    def begin(self):
        logger.info('Beginning...')
        self.enqueue(self.initialize_from_givens)
        self.enqueue(self.push, self.begin_state())

    def run(self):
        self.begin()
        while self.queue:
            self.do_next_in_queue()

    def apply_operation(self, op):
        logger.info('Applying operation: %r', op)
        quality = op.quality
        initial_value = self.qualities.get(quality)
        new_value = op.evaluate(initial_value, qualities=self.qualities)
        self.qualities[quality] = new_value
        logger.info('Quality [%s] was %r, now %r', quality, initial_value, new_value)
        self.send(
            'quality_changed',
            quality = quality,
            initial_value = initial_value,
            new_value = new_value,
        )

    def initialize_from_givens(self):
        logger.info('Initializing from givens: %r', self.givens)
        state = self.qualities
        for op in self.givens:
            self.apply_operation(op)
        self.qualities = state

    @property
    def top_state(self):
        return self.stack[-1] if self.stack else None

    def push(self, state):
        logger.debug('Pushing state: %r', state)
        self.enqueue(self.do_push, state)

    def do_push(self, state):
        top_state = self.top_state
        if top_state is not None:
            logger.info("Pausing state %r", top_state)
            top_state.pause(self)
            self.send('pause_state', state=top_state)

        logger.info("Entering state %r", state)
        self.stack.append(state)
        state.enter(self)
        self.send('enter_state', state=state)

    def pop(self):
        logger.debug('Popping state')
        self.enqueue(self.do_pop)

    def do_pop(self):
        state = self.stack.pop()
        logger.info("Exiting state %r", state)
        state.exit(self)
        self.send('exit_state', state=state)

        top_state = self.top_state
        if top_state is not None:
            logger.info("Resuming state %r", top_state)
            top_state.resume(self)
            self.send('resume_state', state=top_state)

    def send(self, signal_name, **kwargs):
        logger.debug('Sending signal %r, %r', signal_name, kwargs)
        signal = getattr(self.signals, signal_name)
        signal.send(self, **kwargs)

    def get_situation(self, name):
        logger.debug('Getting situation %s', name)
        return queries.query_by_name(name, self.rulebook['Situation'])
