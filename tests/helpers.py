from pprint import pprint

from deepdiff import DeepDiff

import ensure as _ensure

from ravel import types

_ensure.unittest_case.maxDiff = None


def source(text):
    length = len(text)
    return types.Source(
        filename = '',
        start = types.Pos(0, 1, 1),
        end = types.Pos(length, length + 1, length + 1),
        text = text,
    )


class DiffEnsure(_ensure.Ensure):
    def equals(self, other):
        try:
            result = super().equals(other)
        except:
            pprint(DeepDiff(self._subject, other))
            raise
        else:
            return result


ensure = DiffEnsure()
