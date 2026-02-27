import logging.config
from copy import deepcopy
from typing import Any
from typing import Final

from museflow.infrastructure.types import LogHandler
from museflow.infrastructure.types import LogLevel

LOGGER_MUSEFLOW: Final[str] = "museflow"

default_conf: Final[dict[str, Any]] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "message": {
            "format": "%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
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
            "stream": "ext://sys.stdout",
        },
        "cli": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "message",
            "stream": "ext://sys.stdout",
        },
        "cli_alert": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "rich": {
            "class": "rich.logging.RichHandler",
            "formatter": "rich",
            "level": "NOTSET",
            # Optional Rich settings
            "markup": True,
            "rich_tracebacks": True,
            "show_level": True,
            "show_path": True,
            "show_time": True,
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
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "alembic": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "httpx": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def configure_loggers(level: LogLevel, handlers: list[LogHandler], propagate: bool = False) -> None:
    """Configures the application's loggers based on the provided level and handlers.

    This function takes a default logging configuration, modifies the log level and
    handlers for the application's main logger, and applies the same handlers
    to other defined loggers and the root logger.

    Args:
        level: The minimum logging level to set (e.g., "INFO", "DEBUG").
        handlers: A list of handler names (e.g., ["console"], ["rich"]) to use.
        propagate: Whether messages should be propagated to ancestor loggers.
    """
    conf = deepcopy(default_conf)

    # Change level and propagate only for our logger for now.
    conf["loggers"][LOGGER_MUSEFLOW]["level"] = level
    conf["loggers"][LOGGER_MUSEFLOW]["propagate"] = propagate

    # However, change handlers for all loggers defined to use the same.
    for logger in conf["loggers"].keys():
        conf["loggers"][logger]["handlers"] = handlers

    # Without forgetting the root handlers.
    conf["root"]["handlers"] = handlers

    logging.config.dictConfig(conf)
