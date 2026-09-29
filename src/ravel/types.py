import operator as op
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol, TypedDict

import attr
from syml.basetypes import Pos, Source  # noqa

from ravel.exceptions import ConstraintError, EvaluationError
from ravel.utils.data import evaluate_term

# Mirrors ravel.engine.state.QualityValue (importing it here would be circular).
type QualityValue = int | float | str


class QualityLookup(Protocol):
    """Read-only access to current quality values by name."""

    def get(self, name: str, /) -> QualityValue | None: ...


EMPTY_QUALITIES: Final[Mapping[str, QualityValue]] = MappingProxyType({})


_STRING_SAFE_OPERATORS: Final = frozenset({"+", "+=", "="})
_CONCATENATING_OPERATORS: Final = frozenset({"+", "+="})

# Longest string a quality may hold, in characters (generous for prose). ``+`` checks the combined length
# before concatenating, so a doubling ``s += s`` or a long ``s + s + ...`` chain fails with a typed
# EvaluationError instead of building an enormous intermediate string.
MAX_STRING_LENGTH: Final = 65_536


def _reject_string_arithmetic(operator: str, left: Any, right: Any, *, subject: object) -> None:
    """Raise unless string operands only meet ``+``/``+=``/``=`` and any concatenation stays within the cap."""
    if operator not in _STRING_SAFE_OPERATORS and (isinstance(left, str) or isinstance(right, str)):
        raise EvaluationError("%r: operator %r does not accept string operands" % (subject, operator))
    concatenating = operator in _CONCATENATING_OPERATORS and isinstance(left, str) and isinstance(right, str)
    if concatenating and len(left) + len(right) > MAX_STRING_LENGTH:
        raise EvaluationError(
            "%r: concatenation would exceed the maximum string length (%d)" % (subject, MAX_STRING_LENGTH)
        )


@attr.s(slots=True)
class Choice:
    choice: Any = attr.ib()


@attr.s(slots=True)
class End:
    outcome: str = attr.ib()


@attr.s(slots=True, repr=False)
class Comparison:
    quality: Any = attr.ib()
    comparator: Any = attr.ib()
    expression: Any = attr.ib()

    _comparators = {
        ">": op.gt,
        ">=": op.ge,
        "==": op.eq,
        "=": op.eq,
        "<=": op.le,
        "<": op.lt,
        "!=": op.ne,
    }

    def get_comparators(self) -> Callable[[Any, Any], Any]:
        return self._comparators[self.comparator]

    def evaluate(self, qvalue: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES) -> bool:
        current = 0 if qvalue is None else qvalue
        rhs = evaluate_term(self.expression, qualities=qualities, qvalue=current)
        try:
            return bool(self.get_comparators()(current, rhs))
        except (TypeError, ArithmeticError) as error:
            raise EvaluationError("%r: %s" % (self, error)) from error

    def __call__(self, qvalue: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES) -> bool:
        """Evaluate, treating an unevaluable condition as false."""
        try:
            return self.evaluate(qvalue, qualities=qualities)
        except EvaluationError:
            return False

    def check(self, qualities: QualityLookup) -> bool:
        return self(qualities.get(self.quality), qualities=qualities)

    def __repr__(self) -> str:
        return "(%r %s %r)" % (self.quality, self.comparator, self.expression)


@attr.s(slots=True)
class Constraint:
    kind: Literal["min", "max"] = attr.ib()
    value: int | float = attr.ib()

    def apply(self, result: QualityValue) -> QualityValue:
        """Clamp ``result`` to this constraint's bound; a string result is rejected."""
        if isinstance(result, str):
            raise ConstraintError("%s constraint %r cannot be applied to string %r" % (self.kind, self.value, result))
        if self.kind == "min":
            return self.value if result < self.value else result
        return self.value if result > self.value else result


@attr.s(slots=True)
class Effect:
    operation: Any = attr.ib()


@attr.s(slots=True)
class Expression:
    term1: Any = attr.ib()
    operator: Any = attr.ib()
    term2: Any = attr.ib()

    _operators = {
        "+": op.add,
        "-": op.sub,
        "*": op.mul,
        "//": op.floordiv,
        "/": op.truediv,
        "%": op.mod,
    }

    def get_operator(self) -> Callable[[Any, Any], Any]:
        return self._operators[self.operator]

    def evaluate(self, **kwargs: Any) -> Any:
        left = evaluate_term(self.term1, **kwargs)
        right = evaluate_term(self.term2, **kwargs)
        _reject_string_arithmetic(self.operator, left, right, subject=self)
        try:
            return self.get_operator()(left, right)
        except (TypeError, ArithmeticError) as error:
            raise EvaluationError("%r: %s" % (self, error)) from error


@attr.s(slots=True)
class BeginChoices:
    pass


@attr.s(slots=True)
class GetChoice:
    pass


@attr.s(slots=True)
class Operation:
    quality: Any = attr.ib()
    operator: Any = attr.ib()
    expression: Any = attr.ib()
    constraint: Any = attr.ib(default=None)

    _operators = {
        "=": lambda a, b: b,
        "+=": op.add,
        "-=": op.sub,
        "*=": op.mul,
        "//=": op.floordiv,
        "/=": op.truediv,
        "%=": op.mod,
    }

    def get_operator(self) -> Callable[[Any, Any], Any]:
        return self._operators[self.operator]

    def evaluate(
        self, initial_value: QualityValue | None, *, qualities: QualityLookup = EMPTY_QUALITIES
    ) -> QualityValue:
        current = 0 if initial_value is None else initial_value
        rhs = evaluate_term(self.expression, qualities=qualities, qvalue=current)
        _reject_string_arithmetic(self.operator, current, rhs, subject=self)
        try:
            result: QualityValue = self.get_operator()(current, rhs)
        except (TypeError, ArithmeticError) as error:
            raise EvaluationError("%r: %s" % (self, error)) from error
        return self.constraint.apply(result) if self.constraint else result


@attr.s(slots=True)
class Predicate:
    name: Any = attr.ib()
    predicate: Any = attr.ib()

    def check(self, qualities: QualityLookup) -> bool:
        if self.predicate is None:
            return True

        return bool(self.predicate.check(qualities))


@attr.s(slots=True)
class Situation:
    intro: Any = attr.ib()
    directives: Any = attr.ib()


@attr.s(slots=True)
class Text:
    text: Any = attr.ib()
    sticky: Any = attr.ib(default=False, repr=False)
    predicate: Any = attr.ib(default=None, repr=False)

    def check(self, qualities: QualityLookup) -> bool:
        if self.predicate is None:
            return True

        return bool(self.predicate.check(qualities))

    def __str__(self) -> str:
        return str(self.text)


@attr.s(frozen=True, slots=True)
class Value:
    """The ``VALUE`` placeholder: evaluates to the current quality value."""

    def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue:
        return qvalue


VALUE: Final = Value()


@attr.s(frozen=True, slots=True)
class QualityRef:
    """A reference to a quality by name, evaluated against the current qualities."""

    name: str = attr.ib()

    def evaluate(self, *, qualities: QualityLookup = EMPTY_QUALITIES, qvalue: QualityValue = 0) -> QualityValue:
        value = qualities.get(self.name)
        return 0 if value is None else value


@attr.s(slots=True)
class Rule:
    name: Any = attr.ib()
    predicates: Any = attr.ib()


class Ruleset(TypedDict):
    """One concept's compiled rules and the baggage each rule name locates."""

    rules: list[Rule]
    locations: dict[str, object]


class CompiledRulebook(TypedDict):
    """The merged rulebook ``Environment.load()`` returns."""

    metadata: dict[str, str]
    rulebook: dict[str, Ruleset]
    givens: list[Operation]
