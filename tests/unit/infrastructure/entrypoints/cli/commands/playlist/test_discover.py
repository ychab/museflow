from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteAttemptReport
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.playlist.discover import playlist_discover_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.discovery import DiscoveryTasteStrategyFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import AsyncDependencyPatcherFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner
from tests.unit.infrastructure.entrypoints.cli.conftest import spend

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.discover"


class TestPlaylistDiscoverParserCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_discover_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = f"{TARGET_PATH}.playlist_discover_logic"
        strategy = DiscoveryTasteStrategyFactory.build()
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = DiscoverTasteResult(playlist=None, strategy=strategy, reports=[], tracks=[])
            yield patched

    def test__nominal(self, mock_playlist_discover_logic: mock.AsyncMock, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "playlist", "discover", "lo-fi jazz and soul for focus",
                "--email", "test@example.com",
                "--provider", MusicProvider.SPOTIFY,
                "--focus", DiscoveryFocus.EXPANSION,
                "--limit", "15",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

        config = mock_playlist_discover_logic.call_args.kwargs["config"]
        assert config.prompt == "lo-fi jazz and soul for focus"
        assert config.focus == DiscoveryFocus.EXPANSION
        assert config.playlist_limit == 15
        assert config.advisor_limit == 23

    def test__prompt__omitted(self, mock_playlist_discover_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code == 0

        config = mock_playlist_discover_logic.call_args.kwargs["config"]
        assert config.prompt is None
        assert config.focus == DiscoveryFocus.EXPANSION

    def test__model__passed_to_logic(self, mock_playlist_discover_logic: mock.AsyncMock, runner: CliRunner) -> None:
        runner.invoke(app, ["playlist", "discover", "--email", "test@example.com", "--model", "openai/gpt-5-mini"])

        mock_playlist_discover_logic.assert_called_once()
        assert mock_playlist_discover_logic.call_args.kwargs["model"] == "openai/gpt-5-mini"

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param(
                "testtest.com",
                "An email address must have an @-sign",
                id="missing_@",
            ),
            pytest.param(
                "test@test",
                "The part after the @-sign is not valid. It should have a period",
                id="missing_dot",
            ),
        ],
    )
    def test__email__invalid(
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "discover", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    def test__provider__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["playlist", "discover", "--email", "test@example.com", "--provider", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--provider': 'foo' is not" in output

    def test__focus__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["playlist", "discover", "--email", "test@example.com", "--focus", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        choices = ", ".join([f"'{focus}'" for focus in DiscoveryFocus])
        assert f"Invalid value for '--focus': 'foo' is not one of {choices}" in output

    @pytest.mark.parametrize(
        ("limit", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--limit': 0 is not in the range", id="zero"),
            pytest.param(-5, "Invalid value for '--limit': -5 is not in the range", id="min_exceed"),
            pytest.param(31, "Invalid value for '--limit': 31 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--limit': 'foo' is not a valid int range", id="string"),
        ],
    )
    def test__limit__invalid(
        self,
        runner: CliRunner,
        limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["playlist", "discover", "--email", "test@example.com", "--limit", limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestPlaylistDiscoverCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_discover_logic(self) -> Iterable[mock.Mock]:
        target_path = f"{TARGET_PATH}.playlist_discover_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = UserNotFoundError()

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__auth_token_not_found(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = ProviderAuthTokenNotFoundError()

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Auth token not found with email: test@example.com. Did you forget to connect?" in output

    def test__usage__printed_after_the_tracks(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build()

        async def discover(**kwargs: Any) -> DiscoverTasteResult:
            spend(kwargs["meter"])
            return DiscoverTasteResult(playlist=None, strategy=strategy, reports=[], tracks=[])

        mock_playlist_discover_logic.side_effect = discover

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0
        assert result.output.index("dry-run mode") < result.output.index("LLM usage")
        assert "$0.0123" in result.output

    def test__no_new_track__usage_printed(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        async def discover(**kwargs: Any) -> DiscoverTasteResult:
            spend(kwargs["meter"])
            raise DiscoveryTrackNoNewError()

        mock_playlist_discover_logic.side_effect = discover

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code == 1
        assert result.output.index("No new tracks found") < result.output.index("LLM usage")
        assert "$0.0123" in result.output

    def test__taste_profile_not_found(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = TasteProfileNotFoundError()

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No profile found. Run `museflow taste build --name <name>` first." in output

    def test__taste_profile_status_not_ready(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = TasteProfileStatusNotReadyError()

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Taste profile is still being built. Run `museflow taste build` to completion first." in output

    def test__no_track_new_found(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = DiscoveryTrackNoNewError()

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No new tracks found after all attempts" in output

    def test__output__exceptions(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_discover_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__output__playlist_created(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build(suggested_playlist_name="Progressive Horizons")
        playlist = PlaylistFactory.build()

        track_with_album = TrackFactory.build()
        track_without_album = TrackFactory.build(album_name=None)
        mock_playlist_discover_logic.return_value = DiscoverTasteResult(
            playlist=playlist,
            strategy=strategy,
            reports=[],
            tracks=[track_with_album, track_without_album],
        )

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Suggested tracks successfully saved into playlist 'Progressive Horizons'!" in output
        assert f"Saved playlist ID: {playlist.id}" in output
        assert "Rate tracks: museflow rate playlist" in output
        assert "--email" not in output

    def test__output__dry_run(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build()
        mock_playlist_discover_logic.return_value = DiscoverTasteResult(
            playlist=None, strategy=strategy, reports=[], tracks=[]
        )

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Tracks discovered but playlist not created (dry-run mode)" in output

    def test__output__reports_table_rendered(
        self,
        mock_playlist_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build()
        mock_playlist_discover_logic.return_value = DiscoverTasteResult(
            playlist=None,
            strategy=strategy,
            reports=[DiscoverTasteAttemptReport(attempt=1, tracks_suggested=5, tracks_survived=3, tracks_new=2)],
            tracks=[],
        )

        result = runner.invoke(app, ["playlist", "discover", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Discovery Report" in output


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_track_repository",
    "mock_taste_profile_repository",
    "mock_blacklist_repository",
    "mock_playlist_repository",
    "mock_get_provider_library",
)
class TestPlaylistDiscoverLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.discover"

    @pytest.fixture(autouse=True)
    def mock_advisor(
        self,
        mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
    ) -> Iterable[mock.AsyncMock]:
        client = mock.AsyncMock()
        with mock_async_context_dependency_factory(f"{TARGET_PATH}.get_advisor", client) as mock_client:
            yield mock_client

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await playlist_discover_logic(
                "test@example.com",
                provider=MusicProvider.SPOTIFY,
                config=DiscoverTasteConfigInput(),
            )
