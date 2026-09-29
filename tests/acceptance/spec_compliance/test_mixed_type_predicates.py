"""Acceptance: stories whose predicates mix operand types on one quality load and play (ravel-h6v.29)."""

import pytest

from ravel import engine
from ravel.adapters.story_source import MemoryStorySource

pytestmark = pytest.mark.acceptance


def offered(source: str) -> list[str]:
    """Load ``source`` from memory, start it, and return the offered situation locations."""
    step = engine.start(MemoryStorySource({"begin": source}).load())
    return [c.location for o in step.outputs if hasattr(o, "choices") for c in o.choices]


def situation(name: str, *predicates: str) -> str:
    when = "".join(f"      - {p}\n" for p in predicates)
    return f"{name}:\n  - when:\n{when}  - {name} here.\n  - choice:\n      - [Go]Going.\n\n"


class TestMixedTypePredicates:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            (["x = 5", "threshold = 3"], ["begin::both"]),
            (["x = 5", "threshold = 9"], []),
            (["x = 0", "threshold = -1"], []),
            (["x = 5", "threshold = 5"], []),
        ],
    )
    def test_a_story_mixing_a_literal_and_a_quality_bound_offers_the_right_situation(self, given, expected):
        givens = "".join(f"  - {g}\n" for g in given)
        source = f"given:\n{givens}\n" + situation("both", "x > 1", "x > threshold")

        assert offered(source) == expected

    @pytest.mark.parametrize(
        "predicates",
        [("x > 1", "x > y"), ("x > 1", 'x > "a"'), ("x > 1.5", "x > value")],
    )
    def test_each_mixed_type_pair_loads_and_plays(self, predicates):
        source = "given:\n  - x = 5\n  - y = 2\n\n" + situation("mixed", *predicates)

        assert isinstance(offered(source), list)

    def test_a_top_level_when_mixed_with_a_rule_predicate_loads_and_plays(self):
        source = (
            "given:\n  - x = 5\n  - threshold = 2\n\nwhen:\n  - x > 1\n\n"
            + situation("mixed", "x > threshold")
            + situation("plain", "x > 4")
        )

        assert sorted(offered(source)) == ["begin::mixed", "begin::plain"]
