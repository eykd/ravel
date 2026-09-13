from unittest.mock import Mock

import pytest

from ravel.compiler import logger


class TestLogger:
    """Every wrapper is a thin pass-through to the module's stdlib logger."""

    @pytest.mark.parametrize("name", ["debug", "info", "warning", "error", "exception"])
    def test_it_should_delegate_to_the_underlying_logger(self, name, monkeypatch):
        underlying = Mock()
        monkeypatch.setattr(logger, "_logger", underlying)

        getattr(logger, name)("a message %s", "arg", exc_info=True)

        getattr(underlying, name).assert_called_once_with("a message %s", "arg", exc_info=True)
