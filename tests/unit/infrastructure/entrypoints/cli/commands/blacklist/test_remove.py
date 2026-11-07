import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import BlacklistItemNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist.remove import blacklist_remove_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.remove"


class TestBlacklistRemoveParserCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_remove_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_remove_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", str(id1), str(id2)])
        assert result.exit_code == 0

    def test__invalid_item_id(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", "not-a-uuid"])
        assert result.exit_code != 0
        assert "not-a-uuid" in clean_typer_text(result.output)


class TestBlacklistRemoveCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_remove_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_remove_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", str(id1), str(id2)])
        assert result.exit_code == 0

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_blacklist_remove_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_remove_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", str(uuid.uuid4())])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__blacklist_item_not_found(
        self,
        runner: CliRunner,
        mock_blacklist_remove_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_remove_logic.side_effect = BlacklistItemNotFoundError("1 item(s) not found")
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", str(uuid.uuid4())])
        assert result.exit_code != 0
        assert "Error: 1 item(s) not found" in clean_typer_text(result.stderr)

    def test__exceptions(
        self, runner: CliRunner, mock_blacklist_remove_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_blacklist_remove_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["blacklist", "remove", "--email", "test@example.com", str(uuid.uuid4())])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_blacklist_repository")
class TestBlacklistRemoveLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await blacklist_remove_logic(email="unknown@example.com", item_ids=[uuid.uuid4()])
