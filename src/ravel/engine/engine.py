"""The pure run loop: ``start`` a new game and ``choose`` among offered choices."""

from collections.abc import Callable
from typing import Any

from attrs import define, evolve, field

from ravel import queries, types
from ravel.engine.errors import GameOverError, InvalidStateError, NotOfferedError, NotWaitingError
from ravel.engine.outputs import (
    ChoiceOption,
    ChoicesOffered,
    Halted,
    Output,
    QualityChanged,
    SituationEntered,
    SituationExited,
    Step,
    TextShown,
)
from ravel.engine.state import ChoiceBlock, Frame, GameState, LocationId, Outcome, Qualities, Status
from ravel.engine.story import Story
from ravel.utils.strings import get_text


def choice_blocks(situation: types.Situation) -> tuple[ChoiceBlock, ...]:
    """Every choice block in ``situation``, source order.

    Shared by the run loop (``begin_choices``), ``encode_save`` (to compute an anchor), and
    ``engine.resume`` (to resolve one).
    """
    directives = situation.directives
    blocks: list[ChoiceBlock] = []
    ip = 0
    while ip < len(directives):
        if not isinstance(directives[ip], types.BeginChoices):
            ip += 1
            continue
        choices: list[LocationId] = []
        get_choice_ip = ip + 1
        while get_choice_ip < len(directives) and isinstance(directives[get_choice_ip], types.Choice):
            choices.append(directives[get_choice_ip].choice)
            get_choice_ip += 1
        if get_choice_ip < len(directives) and isinstance(directives[get_choice_ip], types.GetChoice):
            blocks.append(ChoiceBlock(choices=tuple(choices), get_choice_ip=get_choice_ip))
        ip = get_choice_ip + 1
    return tuple(blocks)


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

    def _step(
        self, *, stack: tuple[Frame, ...], status: Status, offered: tuple[LocationId, ...], outcome: Outcome | None
    ) -> Step:
        """Snapshot the run's qualities and outputs into a ``Step`` with the given rest-state fields."""
        state = GameState(qualities=self.qualities, stack=stack, status=status, offered=offered, outcome=outcome)
        return Step(state=state, outputs=tuple(self.outputs))

    def rest(self, offered: tuple[ChoiceOption, ...]) -> Step:
        """Offer ``offered`` and return the waiting step."""
        self.outputs.append(ChoicesOffered(offered))
        return self._step(
            stack=tuple(self.stack),
            status=Status.WAITING,
            offered=tuple(option.location for option in offered),
            outcome=None,
        )

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
        """Offer every situation whose predicates hold, most specific first; halt on a dead end."""
        matches = tuple(queries.query("Situation", self.qualities.items, self.story.rulebook["rulebook"]))
        if not matches:
            return self.halt(Outcome("", dead_end=True))
        return self.rest(tuple(ChoiceOption(location, get_text(situation.intro)) for location, situation in matches))

    def halt(self, outcome: Outcome) -> Step:
        """Clear the stack, emit ``Halted``, and return the halted step."""
        self.outputs.append(Halted(outcome.label, outcome.dead_end))
        return self._step(stack=(), status=Status.HALTED, offered=(), outcome=outcome)

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
        """Find this block via ``choice_blocks``, rest on its ``GetChoice``, and wait."""
        situation = self.situation(frame.location)
        for block in choice_blocks(situation):
            if block.get_choice_ip - len(block.choices) == frame.ip + 1:
                self.advance(frame, block.get_choice_ip)
                return self.rest(tuple(self.option(location) for location in block.choices))
        raise InvalidStateError("%r has a choice block without a GetChoice" % frame.location)

    def unreachable(self, frame: Frame, directive: object) -> None:
        raise InvalidStateError("%r reached %r outside a choice block" % (frame.location, directive))

    def end(self, _frame: Frame, end: types.End) -> Step:
        """Halt immediately on ``End(outcome)``, at any stack depth."""
        return self.halt(Outcome(end.outcome, dead_end=False))


# Keyed by directive type, so each handler receives exactly the directive type it declares.
_DISPATCH: dict[type, Callable[[_Run, Frame, Any], Step | None]] = {
    types.Text: _Run.text,
    types.Operation: _Run.operation,
    types.BeginChoices: _Run.begin_choices,
    types.Choice: _Run.unreachable,
    types.GetChoice: _Run.unreachable,
    types.End: _Run.end,
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
