from unittest.mock import Mock

import pytest

from ravel import types
from ravel.vm import machines, states


@pytest.fixture
def vm():
    return machines.VirtualMachine(rulebook=Mock())


def situation(*directives):
    return types.Situation(intro=types.Text("An intro."), directives=list(directives))


class TestPauseAndResume:
    def test_it_should_stop_displaying_while_paused(self, vm):
        state = states.DisplaySituation(situation=situation(types.Text("One."), types.Text("Two.")))

        state.pause(vm)
        assert state.paused is True

        state.display(vm)
        assert state.index == 0

    def test_it_should_pick_up_where_it_left_off_on_resume(self, vm):
        state = states.DisplaySituation(situation=situation(types.Text("One."), types.Text("Two.")))
        state.pause(vm)

        state.resume(vm)

        assert state.paused is False
        assert state.index == 2


class TestDisplay:
    def test_it_should_pop_itself_at_the_end_of_the_directives(self, vm):
        state = states.DisplaySituation(situation=situation(types.Text("One.")))
        vm.stack.append(state)

        state.display(vm)

        assert len(vm.queue) == 1
        vm.do_next_in_queue()
        assert list(vm.stack) == []

    def test_it_should_leave_a_non_empty_queue_alone(self, vm):
        """Something else is already scheduled, so the state must not pop itself."""
        state = states.DisplaySituation(situation=situation(types.Text("One.")))
        vm.stack.append(state)
        vm.enqueue(Mock(__name__="already_queued"))

        state.display(vm)

        assert len(vm.queue) == 1
        assert list(vm.stack) == [state]

    def test_it_should_skip_whitespace_only_text(self):
        """The machine is slotted, so a Mock stands in where send must be watched."""
        vm = Mock()
        state = states.DisplaySituation(situation=situation(types.Text("   \n  ")))

        state.display(vm)

        vm.send.assert_not_called()


class TestHandleOperation:
    def test_it_should_apply_the_operation_to_the_machine(self, vm):
        state = states.DisplaySituation(situation=situation())
        operation = types.Operation(quality="Light", operator="+=", expression=1)

        state.handle_operation(vm, operation)

        assert vm.qualities["Light"] == 1


class TestReceive:
    def test_it_should_push_the_chosen_situation_immediately(self):
        """receive uses do_push, not push: the new state enters without queuing."""
        chosen = situation(types.Text("Chosen."))
        vm = Mock()
        vm.get_situation.return_value = chosen
        state = states.DisplaySituation(situation=situation())

        state.receive(vm, "some::location")

        vm.get_situation.assert_called_once_with("some::location")
        vm.do_push.assert_called_once_with(states.DisplaySituation(situation=chosen))


class TestBaseState:
    """State's hooks are no-ops that concrete states override selectively."""

    def test_it_should_accept_every_transition_without_doing_anything(self, vm):
        state = states.State()

        assert state.enter(vm) is None
        assert state.exit(vm) is None
        assert state.pause(vm) is None
        assert state.resume(vm) is None
        assert state.receive(vm, "data") is None
