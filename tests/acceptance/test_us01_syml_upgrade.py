"""Acceptance test for US1: stories load under syml 1.0.

RED per specs/001-reentrant-vm/tasks.md ravel-8qa.5.1.1 -- expected to FAIL
until the Green leaf (ravel-8qa.5.1.2) re-indents examples/fixtures/spec,
drops the syml mypy override, and deletes rooms.ravel.
"""

from pathlib import Path

import pytest

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

pytestmark = pytest.mark.acceptance

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_ROOT = REPO_ROOT / "examples"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _story_dirs() -> list[Path]:
    return sorted({ravel_file.parent for ravel_file in EXAMPLES_ROOT.rglob("*.ravel")})


def test_every_example_story_loads_under_syml_1_0():
    """AS1-AS3: every examples/* story loads via Environment(...).load() without raising."""
    story_dirs = _story_dirs()
    assert story_dirs, "expected at least one examples/* directory with a *.ravel file"

    failures = {}
    for story_dir in story_dirs:
        name = story_dir.relative_to(EXAMPLES_ROOT).as_posix()
        environment = Environment(loader=FileSystemLoader(base_path=str(story_dir)))
        try:
            environment.load()
        except Exception as exc:  # noqa: BLE001 - collecting every failure, not just the first
            failures[name] = repr(exc)

    assert not failures, f"stories failed to load under syml 1.0: {failures}"


def test_rooms_ravel_deleted_from_cloak():
    """FR-039: examples/cloak/rooms.ravel no longer exists (content merged elsewhere)."""
    assert not (EXAMPLES_ROOT / "cloak" / "rooms.ravel").exists()


def test_syml_mypy_override_removed():
    """FR-003: the syml.* mypy override is dropped once syml ships its own type stubs."""
    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    assert "syml.*" not in pyproject_text
