from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.use_cases.discover_taste import DiscoverTasteResult
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicAdvisorAgent
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.discover.taste import discover_taste_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.music import PlaylistFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.value_objects.discovery import DiscoveryTasteStrategyFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import AsyncDependencyPatcherFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.discover.taste"


@pytest.fixture
def mock_spotify_client(
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    client = mock.AsyncMock(spec=ProviderOAuthPort)
    with mock_async_context_dependency_factory(f"{TARGET_PATH}.get_provider_oauth", client) as mock_client:
        yield mock_client


class TestDiscoverTasteParserCommand:
    @pytest.fixture(autouse=True)
    def mock_discover_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = f"{TARGET_PATH}.discover_taste_logic"
        strategy = DiscoveryTasteStrategyFactory.build()
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = DiscoverTasteResult(playlist=None, strategy=strategy, tracks=[])
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "discover",
                "taste",
                "--email", "test@example.com",
                "--advisor-agent", MusicAdvisorAgent.GEMINI,
                "--provider", MusicProvider.SPOTIFY,
                "--focus", DiscoveryFocus.EXPANSION,
                "--similar-limit", "10",
                "--candidate-limit", "10",
                "--playlist-size", "15",
                "--max-tracks-per-artist", "2",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

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
        result = runner.invoke(app, ["discover", "taste", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    def test__advisor_agent__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--advisor-agent", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--advisor-agent': 'foo' is not" in output

    def test__provider__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--provider", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--provider': 'foo' is not" in output

    def test__focus__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--focus", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        choices = ", ".join([f"'{focus}'" for focus in DiscoveryFocus])
        assert f"Invalid value for '--focus': 'foo' is not one of {choices}" in output

    @pytest.mark.parametrize(
        ("similar_limit", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--similar-limit': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--similar-limit': -15 is not in the range", id="min_exceed"),
            pytest.param(25, "Invalid value for '--similar-limit': 25 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--similar-limit': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__similar_limit__invalid(
        self,
        runner: CliRunner,
        similar_limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--similar-limit", similar_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("candidate_limit", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--candidate-limit': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--candidate-limit': -15 is not in the range", id="min_exceed"),
            pytest.param(25, "Invalid value for '--candidate-limit': 25 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--candidate-limit': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__candidate_limit__invalid(
        self,
        runner: CliRunner,
        candidate_limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--candidate-limit", candidate_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("playlist_size", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--playlist-size': 0 is not in the range", id="zero"),
            pytest.param(-5, "Invalid value for '--playlist-size': -5 is not in the range", id="min_exceed"),
            pytest.param(31, "Invalid value for '--playlist-size': 31 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--playlist-size': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__playlist_size__invalid(
        self,
        runner: CliRunner,
        playlist_size: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--playlist-size", playlist_size],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("max_tracks_per_artist", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--max-tracks-per-artist': 0 is not in the range", id="zero"),
            pytest.param(-1, "Invalid value for '--max-tracks-per-artist': -1 is not in the range", id="min_exceed"),
            pytest.param(11, "Invalid value for '--max-tracks-per-artist': 11 is not in the range", id="max_exceed"),
            pytest.param(
                "foo", "Invalid value for '--max-tracks-per-artist': 'foo' is not a valid integer", id="string"
            ),
        ],
    )
    def test__max_tracks_per_artist__invalid(
        self,
        runner: CliRunner,
        max_tracks_per_artist: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--max-tracks-per-artist", max_tracks_per_artist],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("score_band_width", "expected_msg"),
        [
            pytest.param(0.0, "Invalid value for '--score-band-width': 0.0 is not in the range", id="zero"),
            pytest.param(0.009, "Invalid value for '--score-band-width': 0.009 is not in the range", id="min_exceed"),
            pytest.param(0.6, "Invalid value for '--score-band-width': 0.6 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--score-band-width': 'foo' is not a valid float", id="string"),
        ],
    )
    def test__score_band_width__invalid(
        self,
        runner: CliRunner,
        score_band_width: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["discover", "taste", "--email", "test@example.com", "--score-band-width", score_band_width],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestDiscoverTasteCommand:
    @pytest.fixture(autouse=True)
    def mock_discover_logic(self) -> Iterable[mock.Mock]:
        target_path = f"{TARGET_PATH}.discover_taste_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__auth_token_not_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = ProviderAuthTokenNotFoundError()

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Auth token not found with email: test@example.com. Did you forget to connect?" in output

    def test__taste_profile_not_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = TasteProfileNotFoundException()

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No profile found. Run muse taste build --name <name> first." in output

    def test__no_track_new_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = DiscoveryTrackNoNew()

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No new tracks found" in output

    def test__output__exceptions(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__output__playlist_created(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build(suggested_playlist_name="Progressive Horizons")
        playlist = PlaylistFactory.build()

        track_with_album = TrackFactory.build()
        track_without_album = TrackFactory.build(album=None)
        mock_discover_logic.return_value = DiscoverTasteResult(
            playlist=playlist,
            strategy=strategy,
            tracks=[track_with_album, track_without_album],
        )

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Suggested tracks successfully saved into playlist 'Progressive Horizons'!" in output

    def test__output__dry_run(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        strategy = DiscoveryTasteStrategyFactory.build()
        mock_discover_logic.return_value = DiscoverTasteResult(playlist=None, strategy=strategy, tracks=[])

        result = runner.invoke(app, ["discover", "taste", "--email", "test@example.com", "--dry-run"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Tracks discovered but playlist not created (dry-run mode)" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_auth_token_repository",
    "mock_track_repository",
    "mock_taste_profile_repository",
    "mock_spotify_client",
)
class TestDiscoverTasteLogic:
    @pytest.fixture(autouse=True)
    def mock_advisor_agent(
        self,
        mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
    ) -> Iterable[mock.AsyncMock]:
        client = mock.AsyncMock()
        with mock_async_context_dependency_factory(f"{TARGET_PATH}.get_advisor_agent_adapter", client) as mock_client:
            yield mock_client

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await discover_taste_logic(
                "test@example.com",
                advisor_agent=MusicAdvisorAgent.GEMINI,
                provider=MusicProvider.SPOTIFY,
                config=DiscoverTasteConfigInput(),
            )

    async def test__auth_token__not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError):
            await discover_taste_logic(
                user.email,
                advisor_agent=MusicAdvisorAgent.GEMINI,
                provider=MusicProvider.SPOTIFY,
                config=DiscoverTasteConfigInput(),
            )
