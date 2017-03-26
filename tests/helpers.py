from pprint import pprint

from deepdiff import DeepDiff
from syml.utils import get_text_source


import ensure as _ensure

_ensure.unittest_case.maxDiff = None


def source(text):
    return get_text_source(text, text)


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
