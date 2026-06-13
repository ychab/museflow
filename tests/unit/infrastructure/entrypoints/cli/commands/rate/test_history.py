from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.infrastructure.entrypoints.cli.commands.rate.history import RateHistoryResult
from museflow.infrastructure.entrypoints.cli.commands.rate.history import rate_history_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.music import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.history"


class TestRateHistoryParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_history_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_history_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["rate", "history", "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output


class TestRateHistoryCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_history_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_history_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.return_value = RateHistoryResult(
            rated_count=2, blacklist_track_count=1, blacklist_artist_count=0
        )

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com"])

        assert result.exit_code == 0
        mock_rate_history_logic.assert_awaited_once()
        assert "Saved 2 rating(s)" in clean_typer_text(result.output)

    def test__no_tracks(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.return_value = RateHistoryResult(no_tracks=True)

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "No unrated history tracks." in clean_typer_text(result.output)

    def test__user_not_found(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__auth_token_not_found(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.side_effect = ProviderAuthTokenNotFoundError("No Spotify auth token found")

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com", "--play"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "No Spotify auth token found" in output

    def test__premium_required(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.side_effect = ProviderPremiumRequiredException("Spotify Premium required")

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com", "--play"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Spotify Premium required" in output

    def test__generic_exception(
        self,
        mock_rate_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_history_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["rate", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_track_repository",
    "mock_blacklist_repository",
    "mock_provider_oauth",
    "mock_auth_token_repository",
    "mock_provider_library_factory",
)
class TestRateHistoryLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.history"

    @pytest.fixture
    def mock_builtin_input(self) -> Iterable[mock.Mock]:
        with mock.patch("builtins.input") as patched:
            yield patched

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await rate_history_logic(email="test@example.com", limit=10, reset=False)

    async def test__no_unrated_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        result = await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_track_repository.rate.assert_not_awaited()
        assert result.no_tracks is True

    async def test__nominal__rates_track(
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

        result = await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)
        assert result.rated_count == 1

    async def test__skips_track_on_s_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "s"

        await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_invalid_input(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "abc"

        await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_track_repository.rate.assert_not_awaited()

    async def test__skips_track_on_out_of_range_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
    ) -> None:
        track = TrackFactory.build()
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "15"

        await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_track_repository.rate.assert_not_awaited()

    async def test__blacklists_both_on_low_score(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "2"
        mock_typer_confirm.side_effect = [True, True]

        await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_blacklist_repository.add_track.assert_awaited_once_with(
            user_id=user.id, name=track.name, artist_name="Artist A"
        )
        mock_blacklist_repository.add_artist.assert_awaited_once_with(user_id=user.id, artist_name="Artist A")

    async def test__no_blacklist_when_user_declines(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "2"
        mock_typer_confirm.side_effect = [False, False]

        await rate_history_logic(email=user.email, limit=10, reset=False)

        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__reset__resets_scores_and_fetches_unrated(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.reset_score.return_value = 5
        mock_track_repository.get_list.return_value = []
        mock_typer_confirm.return_value = True

        await rate_history_logic(email=user.email, limit=10, reset=True)

        mock_track_repository.reset_score.assert_awaited_once_with(user_id=user.id, source=TrackSource.HISTORY)
        mock_track_repository.get_list.assert_awaited_once()

    async def test__play__calls_play_track(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        mock_provider_library.play_track.assert_awaited_once_with(track.provider_id)

    async def test__play__no_auth_token__aborts(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError):
            await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        mock_provider_library.play_track.assert_not_awaited()

    async def test__play__premium_required__raises(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_provider_library.play_track.side_effect = ProviderPremiumRequiredException()

        with pytest.raises(ProviderPremiumRequiredException):
            await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        mock_track_repository.rate.assert_not_awaited()

    async def test__play__no_active_device__retry_succeeds(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_builtin_input: mock.Mock,
        mock_typer_prompt: mock.Mock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        track = TrackFactory.build(artists=["Artist A"])
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]
        mock_provider_library.play_track.side_effect = [ProviderNoActiveDeviceException(), mock.DEFAULT]
        mock_typer_prompt.return_value = "7"
        mock_typer_confirm.return_value = False

        await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        assert mock_provider_library.play_track.await_count == 2
        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track.id, score=7)

    async def test__play__no_active_device__retry_fails__stops_loop(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        mock_builtin_input: mock.Mock,
    ) -> None:
        tracks = [TrackFactory.build(), TrackFactory.build()]
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = tracks
        mock_provider_library.play_track.side_effect = [
            ProviderNoActiveDeviceException(),
            ProviderNoActiveDeviceException(),
        ]

        await rate_history_logic(email=user.email, limit=10, reset=False, provider=MusicProvider.SPOTIFY)

        assert mock_provider_library.play_track.await_count == 2
        mock_track_repository.rate.assert_not_awaited()
