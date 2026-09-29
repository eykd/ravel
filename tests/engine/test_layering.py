"""Layering test: ``ravel.engine`` imports only its allowlist and never swallows errors blindly.

An AST scan over every module under ``src/ravel/engine/`` (plan.md, "Dependency rule"). Relative
imports resolve against the importing module's package, so ``from ..app import x`` is caught as
``ravel.app``. The scanner is exercised on synthetic sources first, so a clean package cannot hide a
scanner that rejects nothing.
"""

import ast
from pathlib import Path

import pytest

import ravel.engine

ENGINE_DIR = Path(ravel.engine.__file__).resolve().parent
ENGINE_PACKAGE = "ravel.engine"

ALLOWED_STDLIB = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "enum",
        "functools",
        "hashlib",
        "itertools",
        "json",
        "math",
        "operator",
        "typing",
        "types",
    }
)
ALLOWED_THIRD_PARTY = frozenset({"attrs", "attr"})
ALLOWED_RAVEL = ("ravel.types", "ravel.queries", "ravel.utils", "ravel.engine", "ravel.exceptions")

#: Swallowing these (or everything) hides engine bugs as silent misbehavior (D14).
FORBIDDEN_HANDLERS = frozenset({"IndexError"})


def is_allowed(name):
    """Whether the dotted module ``name`` is on the engine's import allowlist."""
    top = name.split(".")[0]
    if top in ALLOWED_STDLIB or top in ALLOWED_THIRD_PARTY:
        return True
    return any(name == prefix or name.startswith(prefix + ".") for prefix in ALLOWED_RAVEL)


def resolve_from(node, package):
    """The absolute module an ``ImportFrom`` names, resolving ``level`` dots against ``package``."""
    if node.level == 0:
        return node.module
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def imported_modules(tree, package):
    """Yield each import as the candidate module names any one of which would justify it.

    ``from ravel import queries`` imports the submodule ``ravel.queries``, not the package
    ``ravel``, so a from-import is justified by its module or by each ``module.name`` it binds.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield (alias.name,)
        elif isinstance(node, ast.ImportFrom):
            module = resolve_from(node, package)
            for alias in node.names:
                yield (module, "%s.%s" % (module, alias.name))


def import_violations(source, package=ENGINE_PACKAGE):
    """The disallowed imports in ``source``, as they were resolved."""
    tree = ast.parse(source)
    return [candidates[-1] for candidates in imported_modules(tree, package) if not any(map(is_allowed, candidates))]


def handler_violations(source):
    """Line numbers of bare ``except:`` and ``except IndexError:`` handlers in ``source``."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = node.type
        names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
        if caught is None or any(isinstance(n, ast.Name) and n.id in FORBIDDEN_HANDLERS for n in names):
            violations.append(node.lineno)
    return violations


def engine_modules():
    """Each ``.py`` file under the engine package with the package its relative imports resolve in."""
    for path in sorted(ENGINE_DIR.rglob("*.py")):
        relative = path.relative_to(ENGINE_DIR).with_suffix("")
        parts = [ENGINE_PACKAGE, *relative.parts]
        if parts[-1] == "__init__":
            parts.pop()
        else:
            parts = parts[:-1]
        yield path, ".".join(parts)


# --- The scanner itself --------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import syml",
        "import click",
        "import os",
        "import os.path",
        "from os import path",
        "import ravel.app",
        "from ravel.app import x",
        "from ravel import app",
        "from ..app import x",
        "from .. import app",
        "import ravel.cli",
        "from ravel import cli",
        "from .. import cli",
        "from ravel.adapters import files",
        "from ..adapters import files",
        "import sys",
        "import logging",
        "import pathlib",
        "import io",
        "import colorclass",
        "from ravel import environments",
        "from ravel.loaders import FileSystemLoader",
    ],
)
def test_scanner_rejects_a_forbidden_import(source):
    assert import_violations(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "from __future__ import annotations",
        "from collections.abc import Mapping",
        "import hashlib, json, math",
        "from typing import Final",
        "import attrs",
        "from attr import s",
        "from ravel import queries, types",
        "from ravel.utils.strings import get_text",
        "from ravel.engine.state import Frame",
        "from . import state",
        "from .state import Frame",
        "from .. import types",
    ],
)
def test_scanner_accepts_an_allowed_import(source):
    assert import_violations(source) == []


def test_scanner_resolves_relative_imports_against_the_package():
    assert import_violations("from ..app import x", package="ravel.engine") == ["ravel.app.x"]


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    pass\nexcept:\n    pass\n",
        "try:\n    pass\nexcept IndexError:\n    pass\n",
        "try:\n    pass\nexcept (KeyError, IndexError):\n    pass\n",
    ],
)
def test_scanner_rejects_a_blind_handler(source):
    assert handler_violations(source) == [3]


def test_scanner_accepts_a_specific_handler():
    assert handler_violations("try:\n    pass\nexcept KeyError:\n    pass\n") == []


# --- The engine package --------------------------------------------------------------------


def test_the_scan_covers_the_engine_package():
    names = {path.name for path, _package in engine_modules()}

    assert {"__init__.py", "engine.py", "state.py", "outputs.py", "story.py", "errors.py"} <= names


@pytest.mark.parametrize(("path", "package"), list(engine_modules()), ids=lambda value: str(value))
def test_engine_module_imports_only_the_allowlist(path, package):
    assert import_violations(path.read_text(encoding="utf-8"), package) == []


@pytest.mark.parametrize(("path", "package"), list(engine_modules()), ids=lambda value: str(value))
def test_engine_module_has_no_blind_exception_handler(path, package):
    assert handler_violations(path.read_text(encoding="utf-8")) == []
