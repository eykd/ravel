"""Acceptance test for US4 (specs/002-spec-compliance): the engine embeds in any host.

RED per ravel-h6v.5.3.1 -- expected to FAIL until the US4 Green leaves land. Plain pytest (PD-15):
drives the public loader, engine and save surfaces and asserts computed values AND kinds.
"""

import builtins
import io
import math
import os
from pathlib import Path
from typing import Any, Final, NoReturn

import pytest

from ravel import engine
from ravel.adapters.story_source import FileSystemStorySource
from ravel.app.saves import decode_save, encode_save
from ravel.app.session import GameSession
from ravel.engine.state import Qualities, QualityValue
from ravel.engine.story import Story
from ravel.environments import Environment

pytestmark = pytest.mark.acceptance

SRC: Final = (
    "given:\n"
    "  - Location = 'Start'\n"
    "  - Gold = 1\n"
    "\n"
    "start:\n"
    "  - when:\n"
    "      - Location = 'Start'\n"
    "  - Ready.\n"
    "  - choice:\n"
    "      - [Go]Going.\n"
    "      - effect:\n"
    "          - Gold = 2\n"
    "          - Location = 'Done'\n"
    "\n"
    "done:\n"
    "  - when:\n"
    "      - Location = 'Done'\n"
    "  - Finished.\n"
)


class InMemorySaveStore:
    """A dict-backed ``SaveStore`` double."""

    def __init__(self) -> None:
        self._saves: dict[str, bytes] = {}

    def write(self, name: str, data: bytes) -> str:
        self._saves[name] = data
        return name

    def read(self, name: str) -> bytes:
        if name not in self._saves:
            raise FileNotFoundError(name)
        return self._saves[name]


def compile_story(tmp_path: Path) -> Story:
    """Write ``SRC`` as a one-file story on disk and compile it."""
    (tmp_path / "begin.ravel").write_text(SRC, encoding="utf-8")
    return FileSystemStorySource(tmp_path).load()


def _forbid(name: str) -> Any:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"filesystem access: {name}{args!r}")

    return forbidden


def test_us4_as1_in_memory_mapping_compiles_and_plays_with_zero_filesystem_access(tmp_path: Path) -> None:
    """US4-AS1: a mapping of rulebook names to source strings compiles and plays with no filesystem access."""
    from ravel.adapters.story_source import MemoryStorySource  # type: ignore[attr-defined]  # noqa: PLC0415

    (tmp_path / "begin.ravel").write_text(SRC, encoding="utf-8")
    disk_source = FileSystemStorySource(tmp_path)

    with pytest.MonkeyPatch.context() as patch:
        for owner, attr in ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat")):
            patch.setattr(owner, attr, _forbid(f"{owner.__name__}.{attr}"))

        # Positive control: the guard really catches filesystem reads.
        with pytest.raises(AssertionError, match="filesystem access"):
            disk_source.load()

        story = MemoryStorySource({"begin": SRC}).load()
        session = GameSession(story, saves=InMemorySaveStore())
        session.new_game()
        menu = session.menu()
        session.choose(menu[0].location)
        state = session.state

    assert len(menu) == 1
    assert state.qualities.get("Gold") == 2
    assert type(state.qualities.get("Gold")) is int
    assert state.qualities.get("Location") == "Done"


def test_us4_as2_environment_without_loader_fails_with_clear_type_error() -> None:
    """US4-AS2: ``Environment()`` with no loader fails with a clear TypeError."""
    with pytest.raises(TypeError):
        Environment()

    with pytest.raises(TypeError) as excinfo:
        Environment(loader=object())
    assert str(excinfo.value) == "Environment loader must have a callable load(); got object"


def test_us4_as3_stateless_handle_resumes_chooses_and_saves_bytes(tmp_path: Path) -> None:
    """US4-AS3: save bytes -> resume -> choose -> save bytes with no session held; new bytes resume equal."""
    story = compile_story(tmp_path)

    def handle(save: bytes, location: str) -> tuple[bytes, Any]:
        step = engine.choose(story, engine.resume(story, decode_save(save)).state, location)
        return encode_save(story, step.state), step

    first = engine.start(story)
    save = encode_save(story, first.state)
    location = engine.present(story, engine.resume(story, decode_save(save)).state)[0].choices[0].location  # type: ignore[attr-defined]

    new_save, step = handle(save, location)

    assert type(new_save) is bytes
    assert new_save != save
    resumed = engine.resume(story, decode_save(new_save))
    assert resumed.state == step.state
    assert encode_save(story, resumed.state) == new_save


@pytest.mark.parametrize(
    "value",
    [-5, -1.5, -0.0, ""],
    ids=["neg-int", "neg-float", "neg-zero-float", "empty-string"],
)
def test_us4_as5_edge_quality_values_round_trip_equal_and_same_type(tmp_path: Path, value: QualityValue) -> None:
    """US4-AS5: qualities holding -5, -1.5, -0.0 and "" save and resume equal and of the same type."""
    story = compile_story(tmp_path)
    start = engine.start(story).state
    state = start.__class__(
        qualities=Qualities.set(start.qualities, "Probe", value),
        stack=start.stack,
        status=start.status,
        offered=start.offered,
        outcome=start.outcome,
    )

    resumed = engine.resume(story, decode_save(encode_save(story, state))).state
    got = resumed.qualities.get("Probe")

    assert got == value
    assert type(got) is type(value)
    if isinstance(value, float):
        assert math.copysign(1, got) == math.copysign(1, value)
