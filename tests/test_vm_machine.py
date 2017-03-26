from unittest import TestCase
from unittest.mock import Mock

from .helpers import ensure

from ravel import types
from ravel.vm import machines


class MachineTests(TestCase):
    def test_it_should_push_a_state(self):
        machine = machines.VirtualMachine(rulebook=Mock())
        state1 = Mock()
        machine.push(state1)
        machine.do_next_in_queue()
        ensure(machine.stack[0]).is_(state1)

        state2 = Mock()
        machine.push(state2)
        machine.do_next_in_queue()
        ensure(machine.stack[0]).is_(state1)
        ensure(machine.stack[1]).is_(state2)

    def test_it_should_pop_a_state(self):
        state1 = Mock()
        state2 = Mock()
        machine = machines.VirtualMachine(rulebook=Mock(), stack=[state1, state2])
        machine.pop()
        machine.do_next_in_queue()
        ensure(machine.stack).has_length(1)
        ensure(machine.stack[0]).is_(state1)

    def test_it_should_initialize_from_rulebook_givens(self):
        givens = [
            types.Operation(
                quality = 'Foo',
                operator = '=',
                expression = 0,
            )
        ]
        machine = machines.VirtualMachine(rulebook=Mock(), givens=givens)
        machine.initialize_from_givens()
        ensure(machine.qualities).equals({'Foo': 0})
