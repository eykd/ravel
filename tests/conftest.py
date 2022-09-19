import pytest

from ravel import environments


@pytest.fixture
def env():
    return environments.Environment()
