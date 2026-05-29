from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist.purge import purge_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.purge"


class TestPurgeParserCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.purge_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 0
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param("testtest.com", "An email address must have an @-sign", id="missing_@"),
            pytest.param("test@test", "The part after the @-sign is not valid", id="missing_dot"),
        ],
    )
    def test__email__invalid(
        self, runner: CliRunner, email: str, expected_msg: str, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", email, "--yes"])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestPurgeCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.purge_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 3
            yield patched

    def test__with_yes_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "entries" in result.output

    def test__confirmation_accepted(self, runner: CliRunner, mock_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com"], input="y\n")
        assert result.exit_code == 0
        mock_logic.assert_called_once()

    def test__confirmation_aborted(self, runner: CliRunner, mock_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com"], input="n\n")
        assert result.exit_code != 0
        mock_logic.assert_not_called()

    def test__user_not_found(
        self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner) -> None:
        mock_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_blacklist_repository")
class TestPurgeLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await purge_logic(email="unknown@example.com")  # type: ignore[arg-type]
