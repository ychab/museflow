import subprocess
import sys

import pytest


class TestConfigureLoggers:
    @pytest.mark.parametrize("handlers", [["cli", "cli_alert"], ["cli"]])
    def test__cli_warning_uses_current_stdout_once(self, handlers: list[str]) -> None:
        # Logging configuration is process-wide, so keep pytest's handlers untouched.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import logging
from contextlib import redirect_stdout
from io import StringIO
from museflow.infrastructure.config.loggers import configure_loggers

configure_loggers("INFO", {handlers!r})
logger = logging.getLogger("museflow.test")
output = StringIO()
with redirect_stdout(output):
    logger.info("test progress")
    logger.warning("test warning")
print(output.getvalue(), end="")
""",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.count("test progress") == 1
        assert result.stdout.count("test warning") == 1
        assert ("WARNING" in result.stdout) is ("cli_alert" in handlers)
