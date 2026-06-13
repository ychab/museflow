import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.rate.playlist import rate_playlist_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.playlist"


class TestRatePlaylistParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_playlist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_playlist_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__playlist_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", "not-a-uuid"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '[PLAYLIST_ID]'" in output

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "playlist", "--email", "notanemail", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__without_playlist_id(self, mock_rate_playlist_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com"])
        assert result.exit_code == 0
        mock_rate_playlist_logic.assert_awaited_once()


class TestRatePlaylistCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_playlist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_playlist_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, mock_rate_playlist_logic: mock.AsyncMock, runner: CliRunner) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", str(playlist_id)])
        assert result.exit_code == 0
        mock_rate_playlist_logic.assert_awaited_once()

    def test__user_not_found(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = UserNotFound()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__playlist_not_found(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = DiscoveryPlaylistNotFoundError()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Playlist {playlist_id} not found." in output

    def test__auth_token_not_found(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = ProviderAuthTokenNotFoundError("No Spotify auth token found")

        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", "--play"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "No Spotify auth token found" in output

    def test__premium_required(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = ProviderPremiumRequiredException("Spotify Premium required")

        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", "--play"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Spotify Premium required" in output

    def test__generic_exception(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = Exception("Boom")
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "playlist", "--email", "test@example.com", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_discovery_playlist_repository",
    "mock_track_repository",
    "mock_blacklist_repository",
    "mock_provider_oauth",
    "mock_auth_token_repository",
    "mock_provider_library_factory",
)
class TestRatePlaylistLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.playlist"

    @pytest.fixture
    def mock_builtin_input(self) -> Iterable[mock.Mock]:
        with mock.patch("builtins.input") as patched:
            yield patched

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await rate_playlist_logic(email="test@example.com", playlist_id=uuid.uuid4())

    async def test__playlist_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = None

        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await rate_playlist_logic(email=user.email, playlist_id=uuid.uuid4())

    async def test__nominal__rates_track(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)

    async def test__skips_track_on_s_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "s"

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_invalid_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "abc"

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_out_of_range_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "15"

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_track_repository.rate.assert_not_awaited()

    async def test__blacklists_both_on_low_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "2"
        mock_typer_confirm.side_effect = [True, True]

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_blacklist_repository.add_track.assert_awaited_once_with(
            user_id=user.id, name=track.name, artist_name="Artist A"
        )
        mock_blacklist_repository.add_artist.assert_awaited_once_with(user_id=user.id, artist_name="Artist A")

    async def test__no_blacklist_when_user_declines(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "2"
        mock_typer_confirm.side_effect = [False, False]

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id)

        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__no_playlist_id__no_unrated_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        await rate_playlist_logic(email=user.email, playlist_id=None)

        mock_track_repository.rate.assert_not_awaited()

    async def test__no_playlist_id__rates_track(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_playlist_logic(email=user.email, playlist_id=None)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)

    async def test__play__calls_play_track(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id, provider=MusicProvider.SPOTIFY)

        mock_provider_library.play_track.assert_awaited_once_with(track.provider_id)

    async def test__play__no_auth_token__aborts(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError):
            await rate_playlist_logic(email=user.email, playlist_id=uuid.uuid4(), provider=MusicProvider.SPOTIFY)

        mock_provider_library.play_track.assert_not_awaited()

    async def test__play__premium_required__raises(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_provider_library.play_track.side_effect = ProviderPremiumRequiredException()

        with pytest.raises(ProviderPremiumRequiredException):
            await rate_playlist_logic(email=user.email, playlist_id=playlist.id, provider=MusicProvider.SPOTIFY)

        mock_track_repository.rate.assert_not_awaited()

    async def test__play__no_active_device__retry_succeeds(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_builtin_input: mock.Mock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_provider_library.play_track.side_effect = [ProviderNoActiveDeviceException(), mock.DEFAULT]
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id, provider=MusicProvider.SPOTIFY)

        assert mock_provider_library.play_track.await_count == 2
        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)

    async def test__play__no_active_device__retry_fails__stops_loop(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_builtin_input: mock.Mock,
    ) -> None:
        tracks = [TrackFactory.build(), TrackFactory.build()]
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=tracks)
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist
        mock_provider_library.play_track.side_effect = [
            ProviderNoActiveDeviceException(),
            ProviderNoActiveDeviceException(),
        ]

        await rate_playlist_logic(email=user.email, playlist_id=playlist.id, provider=MusicProvider.SPOTIFY)

        assert mock_provider_library.play_track.await_count == 2
        mock_track_repository.rate.assert_not_awaited()
