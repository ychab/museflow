from collections.abc import Iterable
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestEmailOption:
    @pytest.fixture
    def app(self) -> typer.Typer:
        email_app = typer.Typer()

        @email_app.command()
        def show(email: str = EMAIL_OPTION) -> None:
            typer.echo(f"email={email}")

        return email_app

    @pytest.fixture
    def cli_email(self, request: pytest.FixtureRequest) -> Iterable[str | None]:
        with mock.patch.object(app_settings, "CLI_DEFAULT_EMAIL", request.param):
            yield request.param

    @pytest.mark.parametrize("cli_email", ["setting@example.com"], indirect=True)
    def test__setting__fallback(self, app: typer.Typer, runner: CliRunner, cli_email: str) -> None:
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert f"email={cli_email}" in result.output

    @pytest.mark.parametrize("cli_email", ["setting@example.com", None], indirect=True)
    def test__option__wins(self, app: typer.Typer, runner: CliRunner, cli_email: str | None) -> None:
        result = runner.invoke(app, ["--email", "option@example.com"])
        assert result.exit_code == 0
        assert "email=option@example.com" in result.output

    @pytest.mark.parametrize("cli_email", [None, ""], indirect=True)
    def test__missing(
        self,
        app: typer.Typer,
        runner: CliRunner,
        cli_email: str | None,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app)
        assert result.exit_code != 0
        assert "Invalid value for '--email': required, pass it or set MUSEFLOW_CLI_DEFAULT_EMAIL" in clean_typer_text(
            result.output
        )

    @pytest.mark.parametrize("cli_email", ["setting@example.com"], indirect=True)
    def test__option__empty(
        self,
        app: typer.Typer,
        runner: CliRunner,
        cli_email: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["--email", ""])
        assert result.exit_code != 0
        assert "required, pass it or set MUSEFLOW_CLI_DEFAULT_EMAIL" in clean_typer_text(result.output)

    @pytest.mark.parametrize("cli_email", ["not-an-email"], indirect=True)
    def test__setting__invalid(
        self,
        app: typer.Typer,
        runner: CliRunner,
        cli_email: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app)
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)
