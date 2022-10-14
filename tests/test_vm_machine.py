from unittest.mock import Mock

import pytest

from ravel import types
from ravel.vm import machines, runners


@pytest.fixture
def runner(cloak_env):
    return runners.QueueRunner(cloak_env)


@pytest.fixture
def vm(runner):
    runner.vm.begin()
    return runner.vm


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


class TestCloak:
    def advance(self, vm, num=1):
        for _ in range(num):
            vm.do_next_in_queue()

    def test_it_should_begin(self, runner, vm):
        assert vm.qualities == {}
        assert list(vm.stack) == []
        assert len(vm.queue) == 2
        assert runner.all_events == []

    def test_it_should_set_givens(self, runner, vm):
        self.advance(vm, 1)
        assert vm.qualities == {"Bar": 0, "Cloakroom": 0, "Fumbled": 0, "Location": "Intro", "Wearing Cloak": 1}
        assert list(vm.stack) == []
        assert len(vm.queue) == 1
        assert runner.all_events == []

    def test_it_should_push_the_initial_state(self, runner, vm):
        self.advance(vm, 2)
        assert list(vm.stack) == []
        assert len(vm.queue) == 1
        assert runner.all_events == []
