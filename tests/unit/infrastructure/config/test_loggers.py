import json
import logging
import sys
import uuid
from collections.abc import Iterable
from decimal import Decimal
from types import TracebackType

import pytest
from rich.logging import RichHandler

from museflow.infrastructure.config.loggers import LOGGER_MUSEFLOW
from museflow.infrastructure.config.loggers import JsonFormatter
from museflow.infrastructure.config.loggers import configure_loggers
from museflow.infrastructure.config.loggers import console_stderr


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


type ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


class TestJsonFormatter:
    @staticmethod
    def _record(extra: dict[str, object] | None = None, exc_info: ExcInfo | None = None) -> logging.LogRecord:
        logger = logging.getLogger("museflow.tests")
        return logger.makeRecord(
            name=logger.name,
            level=logging.INFO,
            fn="module.py",
            lno=42,
            msg="Tracks: %d found",
            args=(3,),
            exc_info=exc_info,
            func="search",
            extra=extra,
        )

    def test__line__fields(self) -> None:
        record = self._record()
        record.created = 1_700_000_000.123456

        line = json.loads(JsonFormatter().format(record))

        assert line == {
            "timestamp": "2023-11-14T22:13:20.123+00:00",
            "level": "INFO",
            "logger": "museflow.tests",
            "function": "search",
            "line": 42,
            "message": "Tracks: 3 found",
        }

    def test__extra__nested__serialized(self) -> None:
        user_id = uuid.uuid4()
        # A key named after a field of the line stays apart from it
        record = self._record(extra={"user_id": user_id, "cost": Decimal("0.0123"), "found": 3, "level_name": "kept"})

        line = json.loads(JsonFormatter().format(record))

        assert line["level"] == "INFO"
        assert line["extra"] == {"user_id": str(user_id), "cost": "0.0123", "found": 3, "level_name": "kept"}

    def test__uvicorn_color_message__left_out(self) -> None:
        record = self._record(extra={"color_message": "\x1b[32mINFO\x1b[0m"})

        assert "extra" not in json.loads(JsonFormatter().format(record))

    def test__exception__traceback(self) -> None:
        try:
            raise ValueError("Malformed reply")
        except ValueError as e:
            record = self._record(exc_info=(type(e), e, e.__traceback__))

        line = json.loads(JsonFormatter().format(record))

        assert line["exception"].startswith("Traceback (most recent call last):")
        assert line["exception"].endswith("ValueError: Malformed reply")
