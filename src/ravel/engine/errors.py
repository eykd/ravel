"""Errors raised by the engine."""


class EngineError(Exception):
    """Base class for every engine error."""


class NotOfferedError(EngineError):
    """The chosen location is not among the offered choices."""


class GameOverError(EngineError):
    """A choice was made on a halted game."""


class NotWaitingError(EngineError):
    """The state is not waiting for input."""


class InvalidQualityValueError(EngineError):
    """A quality name or value is outside the storable domain.

    Raised for bool, NaN, +/-inf, ints outside signed 64-bit, strs or names holding a lone
    surrogate, and any type other than int, float, or str.
    """


class InvalidStateError(EngineError):
    """A game state is not resumable against its story."""
