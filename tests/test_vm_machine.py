from unittest.mock import Mock

from ravel import types
from ravel.vm import machines


class TestMachine:
    def test_it_should_push_a_state(self):
        machine = machines.VirtualMachine(rulebook=Mock())
        state1 = Mock()
        machine.push(state1)
        machine.do_next_in_queue()
        assert machine.stack[0] is state1

        state2 = Mock()
        machine.push(state2)
        machine.do_next_in_queue()
        assert machine.stack[0] is state1
        assert machine.stack[1] is state2

    def test_it_should_pop_a_state(self):
        state1 = Mock()
        state2 = Mock()
        machine = machines.VirtualMachine(rulebook=Mock(), stack=[state1, state2])
        machine.pop()
        machine.do_next_in_queue()
        assert len(machine.stack) == 1
        assert machine.stack[0] is state1

    def test_it_should_initialize_from_rulebook_givens(self):
        givens = [
            types.Operation(
                quality="Foo",
                operator="=",
                expression=0,
            )
        ]
        machine = machines.VirtualMachine(rulebook=Mock(), givens=givens)
        machine.initialize_from_givens()
        assert machine.qualities == {"Foo": 0}
