"""Plain-data outputs the engine emits while it runs."""

from attrs import frozen

from ravel.engine.state import GameState, LocationId, QualityValue


@frozen
class TextShown:
    """A line of story text."""

    text: str
    sticky: bool = False


@frozen
class ChoiceOption:
    """One offered choice."""

    location: LocationId
    label: str


@frozen
class ChoicesOffered:
    """A non-empty menu of choices."""

    choices: tuple[ChoiceOption, ...]

    def __attrs_post_init__(self) -> None:
        if not self.choices:
            raise ValueError("ChoicesOffered needs at least one choice")


@frozen
class QualityChanged:
    """A quality changed value."""

    name: str
    old: QualityValue | None
    new: QualityValue


@frozen
class SituationEntered:
    """A situation was pushed onto the stack."""

    location: LocationId


@frozen
class SituationExited:
    """A situation was popped off the stack."""

    location: LocationId


@frozen
class Halted:
    """The game ended."""

    outcome: str
    dead_end: bool


@frozen
class StoryChanged:
    """Emitted by ``engine.resume`` when the loaded story no longer matches one or more saved
    frames and they were truncated. Never emitted on a fresh ``start``/``choose``, and never
    emitted by a load against an unchanged story."""

    dropped: tuple[LocationId, ...]  # the dropped frames' locations, bottom (deepest kept) to top


type Output = TextShown | ChoicesOffered | QualityChanged | SituationEntered | SituationExited | Halted | StoryChanged


@frozen
class Step:
    """The state after an engine call and the outputs it emitted."""

    state: GameState
    outputs: tuple[Output, ...]
