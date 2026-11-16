import logging.config
from copy import deepcopy
from typing import Any
from typing import Final

from rich.console import Console

from museflow.infrastructure.config.loggers.formatters import JsonFormatter
from museflow.infrastructure.types import LogHandler
from museflow.infrastructure.types import LogLevel

LOGGER_MUSEFLOW: Final[str] = "museflow"

# Logs go to stderr, so that stdout only carries a command's results. The progress display shares this console: a log
# line then prints above it.
console_stderr: Final[Console] = Console(stderr=True)


default_conf: Final[dict[str, Any]] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": JsonFormatter,
        },
        "rich": {
            # RichHandler ignores the 'format' string usually, but 'datefmt' works
            "format": "%(message)s",
            "datefmt": "[%X]",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
        "rich": {
            "class": "rich.logging.RichHandler",
            "formatter": "rich",
            "level": "NOTSET",
            "console": f"ext://{__name__}.console_stderr",
            # Optional Rich settings
            "markup": False,
            "rich_tracebacks": True,
            "show_level": True,
            "show_path": False,
            "show_time": True,
        },
        "json": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "json",
            "stream": "ext://sys.stderr",
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        LOGGER_MUSEFLOW: {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        # Keeps its startup and shutdown messages, whatever the third-party level.
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        # Follows the third-party level: a proxy usually keeps that trace in production.
        "uvicorn.access": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        # Stays at WARNING: from INFO, it logs the SQL with its parameters (tokens, password hashes).
        "sqlalchemy.engine": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        # Stays at WARNING: from INFO, it logs one line per request with its full URL, query string included.
        "httpx": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
}


def configure_loggers(
    level: LogLevel,
    third_party_level: LogLevel,
    handlers: list[LogHandler],
    propagate: bool = False,
) -> None:
    """Configures the application's loggers based on the provided level and handlers.

    This function takes a default logging configuration, modifies the log level and
    handlers for the application's main logger, and applies the same handlers
    to other defined loggers and the root logger.

    Args:
        level: The minimum logging level of the application (e.g., "INFO", "DEBUG").
        third_party_level: The minimum logging level of the libraries that are not pinned, and of the uvicorn access logs.
        handlers: A list of handler names (e.g., ["console"], ["rich"]) to use.
        propagate: Whether messages should be propagated to ancestor loggers.
    """
    conf = deepcopy(default_conf)

    # Change level and propagate only for our main logger.
    conf["loggers"][LOGGER_MUSEFLOW]["level"] = level
    conf["loggers"][LOGGER_MUSEFLOW]["propagate"] = propagate

    # However, change handlers for all loggers defined to use the same.
    for logger in conf["loggers"].keys():
        conf["loggers"][logger]["handlers"] = handlers

    # Without forgetting the root handlers.
    conf["root"]["handlers"] = handlers
    conf["root"]["level"] = third_party_level
    conf["loggers"]["uvicorn.access"]["level"] = third_party_level

    logging.config.dictConfig(conf)
    # stderr then carries JSON lines only: the progress display sharing the console stays silent
    console_stderr.quiet = "json" in handlers
