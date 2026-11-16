import json
import logging
import uuid
from decimal import Decimal
from types import TracebackType

from museflow.infrastructure.config.loggers.formatters import JsonFormatter

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
