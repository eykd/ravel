from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from attrs import define, field

if TYPE_CHECKING:  # pragma: nocover
    from ravel.types import Choice
    from ravel.vm.states import State


class Event:
    name: str


@define(frozen=True)
class begin(Event):
    name = "begin"


@define(frozen=True)
class end(Event):
    name = "end"


@define(frozen=True)
class enter_state(Event):
    name = "enter_state"
    state: State = field()


@define(frozen=True)
class exit_state(Event):
    name = "exit_state"
    state: State = field()


@define(frozen=True)
class pause_state(Event):
    name = "pause_state"
    state: str = field()


@define(frozen=True)
class resume_state(Event):
    name = "resume_state"
    state: State = field()


@define(frozen=True)
class display_text(Event):
    name = "display_text"
    text: str = field()
    state: State = field()
    sticky: bool = field()


@define(frozen=True)
class begin_display_choices(Event):
    name = "begin_display_choices"


@define(frozen=True)
class display_choice(Event):
    name = "display_choice"
    index: int = field()
    choice: Choice = field()
    text: str = field()
    state: State = field()


@define(frozen=True)
class end_display_choices(Event):
    name = "end_display_choices"


@define(frozen=True)
class waiting_for_input(Event):
    name = "waiting_for_input"
    send_input: Callable = field()
    state: State = field()


@define(frozen=True)
class quality_changed(Event):
    name = "quality_changed"

    quality: str
    initial_value: int
    new_value: int
