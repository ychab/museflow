import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.discover.view import view_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.discovery import DiscoveryPlaylistTrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.discover.view"


class TestViewParserCommand:
    @pytest.fixture(autouse=True)
    def mock_view_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.view_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["discover", "view", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code == 0

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["discover", "view", str(playlist_id), "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__playlist_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["discover", "view", "not-a-uuid", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for 'PLAYLIST_ID'" in output


class TestViewCommand:
    @pytest.fixture(autouse=True)
    def mock_view_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.view_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_view_logic.side_effect = UserNotFound()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "view", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__playlist_not_found(
        self,
        mock_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_view_logic.side_effect = DiscoveryPlaylistNotFoundError()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "view", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Playlist {playlist_id} not found." in output

    def test__generic_exception(
        self,
        mock_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_view_logic.side_effect = Exception("Boom")
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "view", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_discovery_playlist_repository")
class TestViewLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.discover.view"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        playlist_id = uuid.uuid4()

        with pytest.raises(UserNotFound):
            await view_logic(email="test@example.com", playlist_id=playlist_id)

    async def test__playlist_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = None
        playlist_id = uuid.uuid4()

        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await view_logic(email=user.email, playlist_id=playlist_id)

    async def test__nominal_with_tracks_with_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
    ) -> None:
        track_with_score = DiscoveryPlaylistTrackFactory.build(score=8, artist_names=["Artist"])
        track_without_score = DiscoveryPlaylistTrackFactory.build(score=None, artist_names=["Other"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track_with_score, track_without_score])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        await view_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.get.assert_awaited_once_with(user.id, playlist.id)
