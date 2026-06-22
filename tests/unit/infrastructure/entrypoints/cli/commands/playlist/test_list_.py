from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.playlist.list_ import list_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.list_"


class TestListParserCommand:
    @pytest.fixture(autouse=True)
    def mock_list_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["playlist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "list", "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output


class TestListCommand:
    @pytest.fixture(autouse=True)
    def mock_list_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_list_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_list_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["playlist", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_list_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_list_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["playlist", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__empty_playlists(self, mock_list_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_list_logic.return_value = []

        result = runner.invoke(app, ["playlist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No playlists found" in result.output

    def test__with_playlists(self, mock_list_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_list_logic.return_value = [PlaylistFactory.build()]

        result = runner.invoke(app, ["playlist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "Playlists" in result.output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_playlist_repository")
class TestListLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.list_"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await list_logic(email="test@example.com")

    async def test__empty_playlists(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_playlist_repository.list.return_value = []

        result = await list_logic(email=user.email)

        assert result == []

    async def test__with_playlists(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        playlists = PlaylistFactory.batch(2)
        mock_user_repository.get_by_email.return_value = user
        mock_playlist_repository.list.return_value = playlists

        result = await list_logic(email=user.email)

        assert result == playlists
        mock_playlist_repository.list.assert_awaited_once_with(user.id)
