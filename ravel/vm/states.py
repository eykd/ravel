import logging

import attr

from ravel import queries
from ravel.utils.strings import get_text


logger = logging.getLogger('vm.states')


@attr.s
class State:
    def enter(self, vm):
        pass

    def exit(self, vm):
        pass

    def pause(self, vm):
        pass

    def receive(self, vm, data):
        pass


@attr.s
class Begin(State):
    def enter(self, vm):
        vm.push(DisplayPossibleSituations())


@attr.s
class DisplayPossibleSituations(State):
    def query_and_display(self, vm):
        query = queries.query('Situation', vm.qualities.items(), vm.rulebook)
        for n, (location, situation) in enumerate(query):
            vm.send(
                'display_choice',
                index = n,
                choice = location,
                text = get_text(situation.intro),
                state = self,
            )
        vm.send(
            'waiting_for_input',
            send_input = lambda choice: self.receive(vm, choice),
            state = self,
        )

    def enter(self, vm):
        self.query_and_display(vm)

    def resume(self, vm):
        self.query_and_display(vm)

    def receive(self, vm, location):
        situation = vm.get_situation(location)
        vm.push(DisplaySituation(situation=situation))


@attr.s
class DisplaySituation(State):
    situation = attr.ib()
    index = attr.ib(default=0)

    def enter(self, vm):
        self.display(vm)

    def resume(self, vm):
        self.display(vm)

    def display(self, vm):
        while True:
            try:
                directive = self.situation.directives[self.index]
            except IndexError:
                logger.info('End of directives for %r', self)
                if not vm.queue:
                    vm.pop()
                break
            handler = getattr(self, 'handle_' + directive.__class__.__name__.lower())
            handler(vm, directive)
            self.index += 1

    def handle_text(self, vm, directive):
        if directive.check(vm.qualities):
            vm.send(
                'display_text',
                text = get_text(directive),
                state = self,
            )

    def handle_choice(self, vm, directive):
        situation = vm.get_situation(directive.choice)
        vm.send(
            'display_choice',
            index = self.index,
            choice = directive.choice,
            text = get_text(situation.intro),
            state = self,
        )

    def handle_getchoice(self, vm, directive):
        vm.send(
            'waiting_for_input',
            send_input = lambda choice: self.receive(vm, choice),
            state=self,
        )

    def handle_operation(self, vm, directive):
        vm.apply_operation(directive)

    def receive(self, vm, location):
        situation = vm.get_situation(location)
        vm.push(DisplaySituation(situation=situation))
