from unittest import mock

import pytest
from typer.testing import CliRunner

from spotifagent import __version__
from spotifagent.infrastructure.entrypoints.cli.main import app


class TestBaseCommand:
    @pytest.mark.parametrize("cmd_arg", ["--version", "-v"])
    def test__version(self, runner: CliRunner, cmd_arg: str, block_cli_configure_loggers: mock.Mock) -> None:
        result = runner.invoke(app, [cmd_arg])

        assert result.exit_code == 0
        assert f"Spotifagent Version: {__version__}" in result.output

        block_cli_configure_loggers.assert_not_called()

    def test__log_level(self, runner: CliRunner, block_cli_configure_loggers: mock.Mock) -> None:
        @app.command("noop")
        def noop():
            pass

        result = runner.invoke(app, ["--log-level", "DEBUG", "noop"])
        assert result.exit_code == 0

        block_cli_configure_loggers.assert_called_once_with(
            level="DEBUG",
            handlers=mock.ANY,
        )

    def test__log_handler(self, runner: CliRunner, block_cli_configure_loggers: mock.Mock) -> None:
        @app.command("noop")
        def noop():
            pass

        result = runner.invoke(app, ["--log-handler", "null", "noop"])
        assert result.exit_code == 0

        block_cli_configure_loggers.assert_called_once_with(
            level=mock.ANY,
            handlers=["null"],
        )
