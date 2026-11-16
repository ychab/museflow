import json
import logging
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Final


class JsonFormatter(logging.Formatter):
    """Formats a record as one JSON object per line, for a log aggregator: the only output that carries `extra`.

    The `extra` data stays nested under its own key, so that it never clashes with a field of the line.
    """

    # The attributes every record has: any other one was given through `extra`. Uvicorn passes its message with ANSI
    # colours as `color_message`: noise in a JSON line.
    _RECORD_ATTRIBUTES: Final[frozenset[str]] = frozenset(
        [*logging.makeLogRecord({}).__dict__, "message", "asctime", "color_message"]
    )

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if extra := {key: value for key, value in record.__dict__.items() if key not in self._RECORD_ATTRIBUTES}:
            line["extra"] = extra
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        # str() for what JSON cannot hold (a UUID, a Decimal): a log line never fails on its data
        return json.dumps(line, ensure_ascii=False, default=str)
