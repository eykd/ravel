import logging

from attrs import define, field

from ravel import queries
from ravel.utils.strings import get_text
from ravel.vm import events

logger = logging.getLogger("vm.states")


@define
class State:
    def enter(self, vm):  # pragma: nocover
        pass

    def exit(self, vm):  # pragma: nocover
        pass

    def pause(self, vm):  # pragma: nocover
        pass

    def resume(self, vm):  # pragma: nocover
        pass

    def receive(self, vm, data):  # pragma: nocover
        pass


@define
class Begin(State):
    def enter(self, vm):
        vm.push(DisplayPossibleSituations())


@define
class DisplayPossibleSituations(State):
    def query_and_display(self, vm):
        query = queries.query("Situation", vm.qualities.items(), vm.rulebook)
        vm.send(events.begin_display_choices())
        for n, (location, situation) in enumerate(query):
            vm.send(
                events.display_choice(index=n, choice=location, text=get_text(situation.intro), state=self),
            )
        vm.send(events.end_display_choices())
        vm.send(events.waiting_for_input(send_input=lambda choice: self.receive(vm, choice), state=self))

    def enter(self, vm):
        self.query_and_display(vm)

    def resume(self, vm):
        self.query_and_display(vm)

    def receive(self, vm, location):
        situation = vm.get_situation(location)
        vm.push(DisplaySituation(situation=situation))


@define
class DisplaySituation(State):
    situation = field()
    index = field(default=0)
    paused = field(default=False)

    def enter(self, vm):
        self.display(vm)

    def pause(self, vm):
        self.paused = True

    def resume(self, vm):
        self.paused = False
        self.display(vm)

    def display(self, vm):
        while not self.paused:
            try:
                directive = self.situation.directives[self.index]
                logger.info(f"Displaying directive {self.index}: {directive!r}")
            except IndexError:
                logger.info(f"End of directives for {self!r}")
                if not vm.queue:
                    vm.pop()
                break
            handler = getattr(self, "handle_" + directive.__class__.__name__.lower())
            logger.info(f"Running handler: {handler.__name__}")
            handler(vm, directive)
            self.index += 1

    def handle_text(self, vm, directive):
        if directive.check(vm.qualities):
            text = get_text(directive)
            if text.strip():
                vm.send(
                    events.display_text(text=text, state=self, sticky=directive.sticky),
                )

    def handle_choice(self, vm, directive):
        situation = vm.get_situation(directive.choice)
        vm.send(
            events.display_choice(
                index=self.index, choice=directive.choice, text=get_text(situation.intro), state=self
            ),
        )

    def handle_beginchoices(self, vm, directive):
        vm.send(events.begin_display_choices())

    def handle_getchoice(self, vm, directive):
        vm.send(events.end_display_choices())
        vm.send(events.waiting_for_input(send_input=lambda choice: self.receive(vm, choice), state=self))

    def handle_operation(self, vm, directive):
        logger.info(f"Applying operation: {directive!r}")
        vm.apply_operation(directive)

    def receive(self, vm, location):
        situation = vm.get_situation(location)
        vm.do_push(DisplaySituation(situation=situation))
