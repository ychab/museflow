from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste.delete import delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.delete"


class TestTasteDeleteParserCommand:
    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["taste", "delete", "--email", "notanemail", "--name", "my-profile"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    def test__name__missing(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["taste", "delete", "--email", "test@example.com"])
        assert result.exit_code != 0


class TestTasteDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.delete_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__with_yes_flag(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(
            app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile", "--yes"]
        )
        assert result.exit_code == 0
        assert "Taste profile 'my-profile' deleted." in result.output
        mock_delete_logic.assert_awaited_once_with(email="test@example.com", name="my-profile")

    def test__confirmation_accepted(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(
            app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile"], input="y\n"
        )
        assert result.exit_code == 0
        assert "export it first with `taste export`" in result.output
        mock_delete_logic.assert_awaited_once()

    def test__confirmation_declined(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(
            app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile"], input="n\n"
        )
        assert result.exit_code == 1
        mock_delete_logic.assert_not_called()

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile", "-y"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__profile_not_found(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = TasteProfileNotFoundException()
        result = runner.invoke(app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile", "-y"])
        assert result.exit_code != 0
        assert "Taste profile not found with name: my-profile" in clean_typer_text(result.output)

    def test__exception(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["taste", "delete", "--email", "test@example.com", "--name", "my-profile", "-y"])
        assert result.exit_code == 1
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestTasteDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await delete_logic(email="unknown@example.com", name="my-profile")

    async def test__nominal(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        mock_taste_profile_repository.delete.return_value = True

        await delete_logic(email="test@example.com", name="my-profile")

        mock_taste_profile_repository.delete.assert_awaited_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            name="my-profile",
        )
