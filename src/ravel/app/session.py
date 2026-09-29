"""``GameSession``: the single mutable holder of a running (or loaded) game.

Per contracts/session-api.md (2026-09-28 revision): ``load`` = ``saves.read`` -> ``decode_save``
(story-free) -> ``engine.resume(story, saved)`` -> assign -> return ``resume``'s outputs
verbatim. It never calls ``engine.start`` (givens are never re-applied) and never calls
``engine.present`` separately (``resume`` already re-derives the pending menu or halt). The
session assigns ``self._state`` only after the engine or the decoder returned successfully, so a
refused or failed load leaves the live game untouched.
"""

from typing import Final, cast

from ravel.app.ports import SaveStore
from ravel.app.saves import NoGameError, SaveNotFoundError, SaveUnreadableError, decode_save, encode_save
from ravel.engine.engine import choose as engine_choose
from ravel.engine.engine import present as engine_present
from ravel.engine.engine import resume as engine_resume
from ravel.engine.engine import start as engine_start
from ravel.engine.outputs import ChoiceOption, ChoicesOffered, Output
from ravel.engine.state import GameState, LocationId, Status
from ravel.engine.story import Story

DEFAULT_SAVE_NAME: Final = "ravel-save.json"


class GameSession:
    """The single mutable holder of one running (or loaded) game."""

    def __init__(self, story: Story, saves: SaveStore) -> None:
        self._story = story
        self._saves = saves
        self._state: GameState | None = None

    @property
    def story(self) -> Story:
        """The compiled story this session plays; fixed for the session's lifetime."""
        return self._story

    @property
    def state(self) -> GameState:
        """The current game state; raises ``NoGameError`` before any game has started or loaded."""
        if self._state is None:
            raise NoGameError("no game has been started or loaded yet")
        return self._state

    def menu(self) -> tuple[ChoiceOption, ...]:
        """The currently offered choices, or ``()`` unless the game is waiting for one."""
        if self._state is None or self._state.status is not Status.WAITING:
            return ()
        # A WAITING state's ``present`` always yields exactly one ``ChoicesOffered`` (see
        # engine-api.md SS present); the HALTED-only alternative is excluded by the check above.
        output = cast(ChoicesOffered, engine_present(self._story, self._state)[0])
        return output.choices

    def new_game(self) -> tuple[Output, ...]:
        """Start a fresh game, replacing any current state."""
        step = engine_start(self._story)
        self._state = step.state
        return step.outputs

    def choose(self, location: LocationId) -> tuple[Output, ...]:
        """Choose ``location`` from the current state; an ``EngineError`` leaves state untouched."""
        step = engine_choose(self._story, self.state, location)
        self._state = step.state
        return step.outputs

    def save(self, name: str = DEFAULT_SAVE_NAME) -> str:
        """Write the current state to ``name``; raises ``NoGameError`` if no game has started.

        ``SaveTooLargeError`` from ``encode_save`` propagates unchanged, before the store is touched.
        """
        data = encode_save(self._story, self.state)
        return self._saves.write(name, data)

    def load(self, name: str = DEFAULT_SAVE_NAME) -> tuple[Output, ...]:
        """Load ``name``, replacing the current state only on success.

        Raises only ``LoadRefusedError`` subclasses: ``FileNotFoundError`` from ``saves.read`` ->
        ``SaveNotFoundError``; any other ``OSError`` -> ``SaveUnreadableError``; everything
        ``decode_save`` raises is already a ``LoadRefusedError``. ``engine.resume`` never raises.
        """
        try:
            data = self._saves.read(name)
        except FileNotFoundError as error:
            raise SaveNotFoundError("no save file at %r" % name) from error
        except OSError as error:
            reason = error.strerror if error.strerror else str(error)
            raise SaveUnreadableError("cannot read save file %r: %s" % (name, reason)) from error
        saved = decode_save(data)
        step = engine_resume(self._story, saved)
        self._state = step.state
        return step.outputs
