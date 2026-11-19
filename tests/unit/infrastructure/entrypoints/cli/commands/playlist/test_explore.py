from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.explore import CreateExplorationPlaylistConfigInput
from museflow.application.use_cases.playlist_exploration_create import CreateExplorationPlaylistResult
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.taste import ArtistSearch
from museflow.infrastructure.entrypoints.cli.commands.playlist.explore import playlist_explore_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner
from tests.unit.infrastructure.entrypoints.cli.conftest import spend

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.explore"


class TestPlaylistExploreParserCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_explore_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_explore_logic", autospec=True) as patched:
            patched.return_value = CreateExplorationPlaylistResult(playlist=None, tracks=[])
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

    @pytest.mark.parametrize(
        ("limit", "expected_msg"),
        [
            pytest.param(0, "Input should be greater than or equal to 1", id="zero"),
            pytest.param(31, "Input should be less than or equal to 30", id="max_exceed"),
        ],
    )
    def test__limit__invalid(
        self,
        runner: CliRunner,
        limit: int,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com", "--limit", str(limit)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--limit': {expected_msg}" in output


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
        async def explore(**kwargs: Any) -> CreateExplorationPlaylistResult:
            spend(kwargs["meter"])
            raise DiscoveryTrackNoNewError()

        mock_playlist_explore_logic.side_effect = explore

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com"])
        assert result.exit_code == 1
        assert result.output.index("No new tracks found") < result.output.index("LLM call(s)")
        assert "$0.0123" in result.output

    def test__output__playlist_created(
        self,
        mock_playlist_explore_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        playlist = PlaylistFactory.build(name="Friday night")

        async def explore(**kwargs: Any) -> CreateExplorationPlaylistResult:
            spend(kwargs["meter"])
            searches = [ArtistSearch(artist="Nova Lane", rejected=True)]
            await kwargs["progress"].publish(CandidatesFound(attempt=1, searches=searches))
            return CreateExplorationPlaylistResult(
                playlist=playlist,
                tracks=[TrackFactory.build(name="Neon Harbor"), TrackFactory.build(album_name=None)],
            )

        mock_playlist_explore_logic.side_effect = explore

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com", "--verbose"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Neon Harbor" in output
        assert "✓ Playlist Friday night · 2/10 tracks" in output
        assert f"View it: museflow playlist view {playlist.id}" in output
        assert "Only 2/10 tracks found: rate more tracks, so that more favourite artists are known." in output
        # --verbose: the details of each step, then the table per step and model
        assert "Nova Lane search rejected" in clean_typer_text(result.stderr)
        assert output.index("Rate tracks: museflow rate playlist") < output.index("LLM usage")

    def test__output__dry_run(
        self,
        mock_playlist_explore_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_explore_logic.return_value = CreateExplorationPlaylistResult(playlist=None, tracks=[])

        result = runner.invoke(app, ["playlist", "explore", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0

        assert "Dry run: no playlist created" in clean_typer_text(result.stdout)


@pytest.mark.usefixtures("mock_wiring", "mock_user_repository", "mock_build_provider_library")
class TestPlaylistExploreLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    @pytest.fixture(autouse=True)
    def mock_advisor(self, mock_wiring: mock.MagicMock) -> mock.AsyncMock:
        client = mock.AsyncMock()
        mock_wiring.build_advisor.return_value.__aenter__.return_value = client
        return client

    async def test__user__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await playlist_explore_logic(
                "test@example.com",
                provider=MusicProvider.SPOTIFY,
                config=CreateExplorationPlaylistConfigInput(),
                progress=mock_progress,
            )
