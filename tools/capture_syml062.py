"""Capture syml 0.6.2's parse of every ``examples/*`` story.

Run **before** bumping the ``syml`` pin to 1.0, so the Green leaf of the
syml-1.0 upgrade (US1) has a durable baseline to diff its re-indented
examples against. Not a fixture: the pickle lives under
``.specify/scratch/``, which is gitignored, and is never asserted against by
any committed test.

Usage::

    uv run python tools/capture_syml062.py
"""

from __future__ import annotations

import pickle
from pathlib import Path

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_ROOT = REPO_ROOT / "examples"
OUTPUT_PATH = REPO_ROOT / ".specify" / "scratch" / "syml062-dumps.pkl"


def find_story_dirs(examples_root: Path) -> list[Path]:
    """Return every directory under ``examples_root`` containing a ``*.ravel`` file."""
    dirs = {ravel_file.parent for ravel_file in examples_root.rglob("*.ravel")}
    return sorted(dirs)


def capture(examples_root: Path) -> dict[str, dict]:
    """Load every story under ``examples_root`` and return name -> rulebook dict."""
    dumps: dict[str, dict] = {}
    for story_dir in find_story_dirs(examples_root):
        name = story_dir.relative_to(examples_root).as_posix()
        environment = Environment(loader=FileSystemLoader(base_path=str(story_dir)))
        dumps[name] = environment.load()
    return dumps


def main() -> None:
    dumps = capture(EXAMPLES_ROOT)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("wb") as fo:
        pickle.dump(dumps, fo)
    print(f"Captured {len(dumps)} stories to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
