"""Shared fixtures for end-to-end user-story acceptance tests."""

import pytest


@pytest.fixture
def context() -> dict:
    """A plain dict scenario context, shared and mutated across acceptance test steps."""
    return {}
