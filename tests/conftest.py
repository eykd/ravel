import pytest
from path import Path

from ravel import environments

PATH = Path(__file__).abspath().dirname()


@pytest.fixture
def examples_path():
    return PATH.parent / "examples"


@pytest.fixture
def env():
    return environments.Environment()
