import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.domain.exceptions import RateScoreInvalidException
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import rate_logic
from museflow.infrastructure.entrypoints.cli.commands.rate import rate_playlist_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate"


class TestRateParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_rate_playlist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_playlist_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        track_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code == 0

    def test__track_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["rate", "--email", "test@example.com", "not-a-uuid", "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '[TRACK_ID]'" in output

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        track_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "--email", "notanemail", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__playlist_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["rate", "--email", "test@example.com", "--playlist-id", "not-a-uuid"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--playlist-id'" in output


class TestRateCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_rate_playlist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_playlist_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        track_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code == 0
        mock_rate_logic.assert_awaited_once()

    def test__missing_args__exits_when_no_playlist_id(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["rate", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Provide TRACK_ID" in output

    def test__user_not_found(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = UserNotFound()
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__track_not_found(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = TrackNotFoundError()
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Track {track_id} not found." in output

    def test__rate_score_invalid(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = RateScoreInvalidException("Score out of range")
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Score out of range" in output

    def test__generic_exception(
        self,
        mock_rate_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_logic.side_effect = Exception("Boom")
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__playlist_mode__nominal(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "--email", "test@example.com", "--playlist-id", str(playlist_id)])
        assert result.exit_code == 0
        mock_rate_playlist_logic.assert_awaited_once()

    def test__playlist_mode__user_not_found(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = UserNotFound()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", "--playlist-id", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__playlist_mode__playlist_not_found(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = DiscoveryPlaylistNotFoundError()
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", "--playlist-id", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Playlist {playlist_id} not found." in output

    def test__playlist_mode__generic_exception(
        self,
        mock_rate_playlist_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_playlist_logic.side_effect = Exception("Boom")
        playlist_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "--email", "test@example.com", "--playlist-id", str(playlist_id)])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository")
class TestRateLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await rate_logic(track_id=uuid.uuid4(), score=5, email="test@example.com")

    async def test__track_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.rate.side_effect = TrackNotFoundError()

        with pytest.raises(TrackNotFoundError):
            await rate_logic(track_id=uuid.uuid4(), score=5, email=user.email)

    async def test__nominal(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        track_id = uuid.uuid4()

        await rate_logic(track_id=track_id, score=7, email=user.email)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track_id, score=7)


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_discovery_playlist_repository",
    "mock_track_repository",
    "mock_blacklist_repository",
)
class TestRatePlaylistLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await rate_playlist_logic(playlist_id=uuid.uuid4(), email="test@example.com")

    async def test__playlist_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = None

        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await rate_playlist_logic(playlist_id=uuid.uuid4(), email=user.email)

    async def test__nominal__rates_track(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="7"):
            with mock.patch("typer.confirm", return_value=False):
                await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)

    async def test__skips_track_on_s_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="s"):
            await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_invalid_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="abc"):
            await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_out_of_range_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build()
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="15"):
            await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

        mock_track_repository.rate.assert_not_awaited()

    async def test__blacklists_both_on_low_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="2"):
            with mock.patch("typer.confirm", side_effect=[True, True]):
                await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

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
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        playlist = DiscoveryPlaylistFactory.build(user_id=user.id, tracks=[track])
        mock_user_repository.get_by_email.return_value = user
        mock_discovery_playlist_repository.get.return_value = playlist

        with mock.patch("typer.prompt", return_value="2"):
            with mock.patch("typer.confirm", side_effect=[False, False]):
                await rate_playlist_logic(playlist_id=playlist.id, email=user.email)

        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()
