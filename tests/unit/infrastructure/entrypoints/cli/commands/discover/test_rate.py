import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.discover.rate import rate_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.discovery import DiscoveryPlaylistTrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.discover.rate"


class TestRateParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["discover", "rate", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code == 0

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["discover", "rate", str(playlist_id), "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__playlist_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["discover", "rate", "not-a-uuid", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for 'PLAYLIST_ID'" in output


class TestRateCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = UserNotFound()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "rate", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__playlist_not_found(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = DiscoveryPlaylistNotFoundError()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "rate", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Playlist {playlist_id} not found." in output

    def test__generic_exception(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = Exception("Boom")
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["discover", "rate", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_discovery_playlist_repository",
    "mock_blacklist_repository",
)
class TestRateLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.discover.rate"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        playlist_id = uuid.uuid4()

        with pytest.raises(UserNotFound):
            await rate_logic(email="test@example.com", playlist_id=playlist_id)

    async def test__playlist_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = None

        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await rate_logic(email=user.email, playlist_id=uuid.uuid4())

    async def test__skip_all_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Some Artist"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="s"):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.rate_track.assert_not_awaited()
        mock_blacklist_repository.add_track.assert_not_awaited()

    async def test__valid_score_above_threshold(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Good Artist"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        # Score 7 is above the default threshold of 3
        with mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="7"):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.rate_track.assert_awaited_once_with(user.id, track.id, 7)
        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__invalid_score_out_of_range(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Some Artist"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        # Score 15 is outside 0-10
        with mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="15"):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.rate_track.assert_not_awaited()

    async def test__invalid_score_non_integer(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Some Artist"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="abc"):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.rate_track.assert_not_awaited()

    async def test__score_below_threshold_blacklist_both(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Bad Artist", "Other"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        # Score 2 is below threshold 3, confirm both blacklists
        with (
            mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="2"),
            mock.patch(f"{TARGET_PATH}.typer.confirm", return_value=True),
        ):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_blacklist_repository.add_track.assert_awaited_once()
        mock_blacklist_repository.add_artist.assert_awaited_once()

    async def test__score_below_threshold_no_blacklist(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = DiscoveryPlaylistTrackFactory.build(artist_names=["Bad Artist"])
        playlist = DiscoveryPlaylistFactory.build(tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        # Score 1 is below threshold 3, but confirm False for both blacklists
        with (
            mock.patch(f"{TARGET_PATH}.typer.prompt", return_value="1"),
            mock.patch(f"{TARGET_PATH}.typer.confirm", return_value=False),
        ):
            await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__empty_playlist(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        playlist = DiscoveryPlaylistFactory.build(tracks=[])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        await rate_logic(email=user.email, playlist_id=playlist.id)

        mock_discovery_playlist_repository.rate_track.assert_not_awaited()
