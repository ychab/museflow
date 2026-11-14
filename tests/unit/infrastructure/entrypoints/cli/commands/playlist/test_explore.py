from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.explore import ExploreArtistsConfigInput
from museflow.application.use_cases.artists_explore import ExploreArtistsAttemptReport
from museflow.application.use_cases.artists_explore import ExploreArtistsResult
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.playlist.explore import playlist_explore_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import AsyncDependencyPatcherFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner
from tests.unit.infrastructure.entrypoints.cli.conftest import spend

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.explore"


class TestPlaylistExploreParserCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_explore_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_explore_logic", autospec=True) as patched:
            patched.return_value = ExploreArtistsResult(playlist=None, reports=[], tracks=[])
            yield patched

    def test__nominal(self, mock_playlist_explore_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "playlist", "explore", "calm and acoustic",
                "--email", "test@example.com",
                "--provider", MusicProvider.SPOTIFY,
                "--model", "openai/gpt-5-mini",
                "--title", "Friday night",
                "--dry-run",
                "--limit", "15",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

        kwargs = mock_playlist_explore_logic.call_args.kwargs
        assert kwargs["model"] == "openai/gpt-5-mini"
        config = kwargs["config"]
        assert config.prompt == "calm and acoustic"
        assert config.title == "Friday night"
        assert config.dry_run is True
        assert config.playlist_limit == 15
        assert config.picks_limit == 23
        assert (config.artists_limit, config.artists_per_attempt) == (20, 5)
        assert config.catalogue_tracks_pages == 10
        assert config.artist_tracks_concurrency == 1

    def test__prompt__omitted(self, mock_playlist_explore_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com"])
        assert result.exit_code == 0

        assert mock_playlist_explore_logic.call_args.kwargs["config"].prompt is None

    @pytest.mark.parametrize("limit", [0, 31])
    def test__limit__invalid(self, runner: CliRunner, limit: int, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com", "--limit", str(limit)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--limit': {limit} is not in the range" in output


class TestPlaylistExploreCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_explore_logic(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{TARGET_PATH}.playlist_explore_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.mark.parametrize(
        ("error", "expected_msg"),
        [
            pytest.param(UserNotFoundError(), "User not found with email: test@example.com", id="user_not_found"),
            pytest.param(
                ProviderAuthTokenNotFoundError(),
                "Auth token not found with email: test@example.com. Did you forget to connect?",
                id="auth_token_not_found",
            ),
            pytest.param(
                DiscoveryTrackNoNewError(),
                "No new tracks found: rate tracks or import your history",
                id="no_new_track",
            ),
            pytest.param(Exception("Boom"), "Error: Boom", id="unexpected"),
        ],
    )
    def test__errors(
        self,
        mock_playlist_explore_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        error: Exception,
        expected_msg: str,
    ) -> None:
        mock_playlist_explore_logic.side_effect = error

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com"])
        assert result.exit_code != 0

        assert expected_msg in clean_typer_text(result.stderr)

    def test__no_new_track__usage_printed(
        self, mock_playlist_explore_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        async def explore(**kwargs: Any) -> ExploreArtistsResult:
            spend(kwargs["meter"])
            raise DiscoveryTrackNoNewError()

        mock_playlist_explore_logic.side_effect = explore

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com"])
        assert result.exit_code == 1
        assert result.output.index("No new tracks found") < result.output.index("LLM usage")
        assert "$0.0123" in result.output

    def test__output__playlist_created(
        self,
        mock_playlist_explore_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        playlist = PlaylistFactory.build(name="Friday night")

        async def explore(**kwargs: Any) -> ExploreArtistsResult:
            spend(kwargs["meter"])
            return ExploreArtistsResult(
                playlist=playlist,
                reports=[ExploreArtistsAttemptReport(attempt=1, artists=5, candidates=653, tracks_picked=15)],
                tracks=[TrackFactory.build(name="Neon Harbor"), TrackFactory.build(album_name=None)],
            )

        mock_playlist_explore_logic.side_effect = explore

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Exploration Report" in output
        assert "653" in output
        assert "Neon Harbor" in output
        assert "Explored tracks successfully saved into playlist 'Friday night'!" in output
        assert f"Saved playlist ID: {playlist.id}" in output
        assert output.index("Rate tracks: museflow rate playlist") < output.index("LLM usage")

    def test__output__dry_run(
        self,
        mock_playlist_explore_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_explore_logic.return_value = ExploreArtistsResult(playlist=None, reports=[], tracks=[])

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0

        assert "Tracks explored but playlist not created (dry-run mode)" in clean_typer_text(result.stdout)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_get_provider_library")
class TestPlaylistExploreLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    @pytest.fixture(autouse=True)
    def mock_advisor(
        self,
        mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
    ) -> Iterable[mock.AsyncMock]:
        with mock_async_context_dependency_factory(f"{TARGET_PATH}.get_advisor", mock.AsyncMock()) as mock_client:
            yield mock_client

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await playlist_explore_logic(
                "test@example.com",
                provider=MusicProvider.SPOTIFY,
                config=ExploreArtistsConfigInput(),
            )
