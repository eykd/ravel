from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from ravel.types import Comparison
from ravel.utils.strings import get_text_source


def source(text):
    return get_text_source(text, text)


class Any:
    def __eq__(self, other):
        return True


@contextmanager
def strict_conditions() -> Iterator[None]:
    """Make conditions raise ``EvaluationError`` instead of failing soft.

    Shipped stories must never hit the soft-failure path; inside this context a broken
    condition surfaces as an exception rather than silently changing play.
    """

    def strict_check(self: Comparison, qualities):  # type: ignore[no-untyped-def]
        return self.evaluate(qualities.get(self.quality), qualities=qualities)

    def strict_call(self: Comparison, qvalue, **kwargs):  # type: ignore[no-untyped-def]
        return self.evaluate(qvalue, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Comparison, "check", strict_check)
        patch.setattr(Comparison, "__call__", strict_call)
        yield
