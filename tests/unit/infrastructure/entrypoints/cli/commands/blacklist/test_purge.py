from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist.purge import blacklist_purge_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.purge"


class TestBlacklistPurgeParserCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_purge_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_purge_logic", new_callable=mock.AsyncMock) as patched:
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
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", email, "--yes"])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestBlacklistPurgeCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_purge_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_purge_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 3
            yield patched

    def test__with_yes_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0
        assert "Deleted 3 blacklist entries of test@example.com." in result.output

    def test__confirmation_accepted(self, runner: CliRunner, mock_blacklist_purge_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com"], input="y\n")
        assert result.exit_code == 0
        assert "Delete the entire blacklist of test@example.com?" in result.output
        mock_blacklist_purge_logic.assert_called_once()

    def test__confirmation_aborted(self, runner: CliRunner, mock_blacklist_purge_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com"], input="n\n")
        assert result.exit_code != 0
        mock_blacklist_purge_logic.assert_not_called()

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_blacklist_purge_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_purge_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(
        self, runner: CliRunner, mock_blacklist_purge_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_blacklist_purge_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["blacklist", "purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_blacklist_repository")
class TestBlacklistPurgeLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await blacklist_purge_logic(email="unknown@example.com")
