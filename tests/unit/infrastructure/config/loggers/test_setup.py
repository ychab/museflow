import logging
import sys
from collections.abc import Iterable

import pytest
from rich.logging import RichHandler

from museflow.infrastructure.config.loggers.formatters import JsonFormatter
from museflow.infrastructure.config.loggers.setup import LOGGER_MUSEFLOW
from museflow.infrastructure.config.loggers.setup import configure_loggers
from museflow.infrastructure.config.loggers.setup import console_stderr


class TestConfigureLoggers:
    @pytest.fixture(autouse=True)
    def restore_test_loggers(self) -> Iterable[None]:
        yield
        # Back to the session configuration of tests/conftest.py
        configure_loggers(level="DEBUG", third_party_level="WARNING", handlers=["null"], propagate=True)

    def test__rich__writes_to_stderr_without_path(self) -> None:
        configure_loggers(level="INFO", third_party_level="WARNING", handlers=["rich"])

        [handler] = logging.getLogger(LOGGER_MUSEFLOW).handlers
        assert isinstance(handler, RichHandler)
        assert handler.console is console_stderr
        assert console_stderr.stderr is True
        assert handler._log_render.show_path is False

    def test__console__writes_to_stderr(self) -> None:
        configure_loggers(level="INFO", third_party_level="WARNING", handlers=["console"])

        [handler] = logging.getLogger(LOGGER_MUSEFLOW).handlers
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test__json__writes_to_stderr__progress_silenced(self) -> None:
        configure_loggers(level="INFO", third_party_level="WARNING", handlers=["json"])

        [handler] = logging.getLogger(LOGGER_MUSEFLOW).handlers
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, JsonFormatter)
        assert handler.stream is sys.stderr
        # stderr carries JSON lines only
        assert console_stderr.quiet is True

        # Another handler gives the progress display back
        configure_loggers(level="INFO", third_party_level="WARNING", handlers=["rich"])
        assert console_stderr.quiet is False
