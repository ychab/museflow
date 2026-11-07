from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.users.delete import users_delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.users.delete"


class TestUsersDeleteParserCommand:
    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["users", "delete", "--email", "notanemail"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    @pytest.fixture
    def cli_email(self) -> Iterable[str]:
        with mock.patch.object(app_settings, "CLI_DEFAULT_EMAIL", "setting@example.com") as patched:
            yield patched

    @pytest.mark.usefixtures("cli_email")
    def test__email__missing__setting_ignored(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["users", "delete", "--yes"])
        assert result.exit_code != 0
        assert "Missing option '--email'" in clean_typer_text(result.output)


class TestUsersDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_users_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.users_delete_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__with_yes_flag(self, runner: CliRunner, mock_users_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["users", "delete", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0
        assert "User test@example.com deleted." in result.output
        mock_users_delete_logic.assert_awaited_once_with(email="test@example.com")

    def test__confirmation_accepted(
        self,
        runner: CliRunner,
        mock_users_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["users", "delete", "--email", "test@example.com"], input="y\n")
        assert result.exit_code == 0
        assert "This cannot be undone" in clean_typer_text(result.output)
        mock_users_delete_logic.assert_awaited_once()

    def test__confirmation_declined(self, runner: CliRunner, mock_users_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["users", "delete", "--email", "test@example.com"], input="n\n")
        assert result.exit_code == 1
        mock_users_delete_logic.assert_not_called()

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_users_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_users_delete_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["users", "delete", "--email", "test@example.com", "--yes"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exception(
        self,
        runner: CliRunner,
        mock_users_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_users_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["users", "delete", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 1
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestUsersDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await users_delete_logic(email="unknown@example.com")

        mock_user_repository.delete.assert_not_called()
