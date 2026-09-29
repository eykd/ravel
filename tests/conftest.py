from pathlib import Path

import pytest

from ravel.environments import Environment
from ravel.loaders import FileSystemLoader

from .helpers import strict_conditions as _strict_conditions

PATH = Path(__file__).resolve().parent


@pytest.fixture
def examples_path():
    return PATH.parent / "examples"


@pytest.fixture
def env():
    return Environment()


@pytest.fixture
def cloak_env(examples_path):
    return Environment(
        loader=FileSystemLoader(base_path=examples_path / "cloak"),
    )


@pytest.fixture
def strict_conditions():
    with _strict_conditions():
        yield
