"""The pure run loop: ``start`` a new game and ``choose`` among offered choices."""

from collections.abc import Callable
from typing import Any

from attrs import define, evolve, field

from ravel import queries, types
from ravel.engine.errors import GameOverError, InvalidStateError, NotOfferedError, NotWaitingError
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Output,
    QualityChanged,
    SituationEntered,
    SituationExited,
    Step,
    TextShown,
)
from ravel.engine.state import Frame, GameState, LocationId, Qualities, Status
from ravel.engine.story import Story
from ravel.utils.strings import get_text


def _apply_operation(qualities: Qualities, operation: types.Operation) -> tuple[Qualities, QualityChanged]:
    """Apply ``operation`` to ``qualities``; the one choke point every quality change passes through.

    ``Qualities.set`` validates the result, raising ``InvalidQualityValueError`` for a value outside
    the storable domain. ``min``/``max`` constraints are not applied (an inherited gap).
    """
    old = qualities.get(operation.quality)
    new = operation.evaluate(old, qualities=qualities)
    return qualities.set(operation.quality, new), QualityChanged(operation.quality, old, new)


@define
class _Run:
    """The scratch state of one engine call; never escapes it."""

    story: Story
    qualities: Qualities
    stack: list[Frame]
    outputs: list[Output] = field(factory=list)

    def rest(self, offered: tuple[ChoiceOption, ...]) -> Step:
        """Offer ``offered`` and return the waiting step."""
        self.outputs.append(ChoicesOffered(offered))
        state = GameState(
            qualities=self.qualities,
            stack=tuple(self.stack),
            status=Status.WAITING,
            offered=tuple(option.location for option in offered),
            outcome=None,
        )
        return Step(state=state, outputs=tuple(self.outputs))

    def enter(self, location: LocationId) -> None:
        """Push ``location`` onto the stack at its first directive."""
        self.stack.append(Frame(location, 0))
        self.outputs.append(SituationEntered(location))

    def situation(self, location: LocationId) -> types.Situation:
        try:
            return self.story.situation(location)
        except KeyError:
            raise InvalidStateError("%r is not a situation in this story" % location) from None

    def option(self, location: LocationId) -> ChoiceOption:
        return ChoiceOption(location, get_text(self.situation(location).intro))

    def run(self) -> Step:
        """Run until the game waits for a choice."""
        while True:
            if not self.stack:
                return self.query()
            frame = self.stack[-1]
            directives = self.situation(frame.location).directives
            if frame.ip >= len(directives):
                self.stack.pop()
                self.outputs.append(SituationExited(frame.location))
                continue
            if frame.ip < 0:
                raise InvalidStateError("%r has no directive at index %d" % (frame.location, frame.ip))
            directive = directives[frame.ip]
            handler = _DISPATCH.get(type(directive))
            if handler is None:
                raise InvalidStateError("%r cannot run directive %r" % (frame.location, directive))
            step = handler(self, frame, directive)
            if step is not None:
                return step

    def query(self) -> Step:
        """Offer every situation whose predicates hold, most specific first."""
        matches = queries.query("Situation", self.qualities.items, self.story.rulebook["rulebook"])
        return self.rest(tuple(ChoiceOption(location, get_text(situation.intro)) for location, situation in matches))

    def advance(self, frame: Frame, ip: int) -> None:
        self.stack[-1] = evolve(frame, ip=ip)

    def text(self, frame: Frame, text: types.Text) -> None:
        if text.check(self.qualities) and text.text.strip():
            self.outputs.append(TextShown(text.text, text.sticky))
        self.advance(frame, frame.ip + 1)

    def operation(self, frame: Frame, operation: types.Operation) -> None:
        self.qualities, change = _apply_operation(self.qualities, operation)
        self.outputs.append(change)
        self.advance(frame, frame.ip + 1)

    def begin_choices(self, frame: Frame, _directive: types.BeginChoices) -> Step:
        """Gather the block's choices, rest on its ``GetChoice``, and wait."""
        directives = self.situation(frame.location).directives
        ip = frame.ip + 1
        choices: list[ChoiceOption] = []
        while ip < len(directives) and isinstance(directives[ip], types.Choice):
            choices.append(self.option(directives[ip].choice))
            ip += 1
        if ip >= len(directives) or not isinstance(directives[ip], types.GetChoice):
            raise InvalidStateError("%r has a choice block without a GetChoice" % frame.location)
        self.advance(frame, ip)
        return self.rest(tuple(choices))

    def unreachable(self, frame: Frame, directive: object) -> None:
        raise InvalidStateError("%r reached %r outside a choice block" % (frame.location, directive))


# Keyed by directive type, so each handler receives exactly the directive type it declares.
_DISPATCH: dict[type, Callable[[_Run, Frame, Any], Step | None]] = {
    types.Text: _Run.text,
    types.Operation: _Run.operation,
    types.BeginChoices: _Run.begin_choices,
    types.Choice: _Run.unreachable,
    types.GetChoice: _Run.unreachable,
}


def start(story: Story) -> Step:
    """Apply ``story``'s givens once each, then run to the first menu or halt."""
    run = _Run(story=story, qualities=Qualities(), stack=[])
    for given in story.givens:
        run.qualities, change = _apply_operation(run.qualities, given)
        run.outputs.append(change)
    return run.run()


def choose(story: Story, state: GameState, location: LocationId) -> Step:
    """Enter the offered ``location`` from a waiting ``state`` and run to the next wait or halt."""
    if state.status is Status.HALTED:
        label = "" if state.outcome is None else state.outcome.label
        raise GameOverError("the game is over (outcome: %r)" % label)
    if state.status is not Status.WAITING:
        raise NotWaitingError("the game is not waiting for a choice (status: %s)" % state.status)
    if location not in state.offered:
        raise NotOfferedError("%r is not an offered choice; offered: %r" % (location, list(state.offered)))
    run = _Run(story=story, qualities=state.qualities, stack=list(state.stack))
    if run.stack:
        top = run.stack[-1]
        run.advance(top, top.ip + 1)
    run.enter(location)
    return run.run()
