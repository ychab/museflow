from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.use_cases.advisor_discover import DiscoveryConfigInput
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import DiscoveryTrackNoReconciledFound
from museflow.domain.exceptions import DiscoveryTrackNoSeedFound
from museflow.domain.exceptions import DiscoveryTrackNoSimilarFound
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.infrastructure.entrypoints.cli.commands.spotify.discover import discover_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.music import PlaylistFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestSpotifyDiscoverParserCommand:
    @pytest.fixture(autouse=True)
    def mock_discover_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.discover.discover_logic"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    def test__nominal(self, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "spotify",
                "discover",
                "--email", "test@example.com",
                "--advisor", MusicAdvisor.LASTFM,
                "--seed-top",
                "--seed-saved",
                "--seed-order-by", TrackOrderBy.RANDOM,
                "--seed-sort-order", SortOrder.DESC,
                "--seed-limit", "20",
                "--similar-limit", "10",
                "--candidate-limit", "10",
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
        result = runner.invoke(app, ["spotify", "discover", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    def test__advisor__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["spotify", "discover", "--email", "test@example.com", "--advisor", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        choices = ", ".join([f"'{advisor}'" for advisor in MusicAdvisor])
        assert f"Invalid value for '--advisor': 'foo' is not one of {choices}" in output

    def test__seed_order_by__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["spotify", "discover", "--email", "test@example.com", "--seed-order-by", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        choices = ", ".join([f"'{order_by}'" for order_by in TrackOrderBy])
        assert f"Invalid value for '--seed-order-by': 'foo' is not one of {choices}" in output

    def test__seed_sort_order__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["spotify", "discover", "--email", "test@example.com", "--seed-sort-order", "foo"],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        choices = ", ".join([f"'{sort_order}'" for sort_order in SortOrder])
        assert f"Invalid value for '--seed-sort-order': 'foo' is not one of {choices}" in output

    @pytest.mark.parametrize(
        ("seed_limit", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--seed-limit': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--seed-limit': -15 is not in the range", id="min_exceed"),
            pytest.param(55, "Invalid value for '--seed-limit': 55 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--seed-limit': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__seed_limit__invalid(
        self,
        runner: CliRunner,
        seed_limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["spotify", "discover", "--email", "test@example.com", "--seed-limit", seed_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

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
            ["spotify", "discover", "--email", "test@example.com", "--similar-limit", similar_limit],
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
            ["spotify", "discover", "--email", "test@example.com", "--candidate-limit", candidate_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestSpotifyDiscoverCommand:
    @pytest.fixture(autouse=True)
    def mock_discover_logic(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.discover.discover_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
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

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Auth token not found with email: test@example.com. Did you forget to connect?" in output

    def test__no_track_seed_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = DiscoveryTrackNoSeedFound()

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No seed tracks founded" in output

    def test__no_track_similar_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = DiscoveryTrackNoSimilarFound()

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No similar tracks founded" in output

    def test__no_track_reconciled_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = DiscoveryTrackNoReconciledFound()

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No reconciled tracks founded" in output

    def test__no_track_new_found(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = DiscoveryTrackNoNew()

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No new tracks founded" in output

    def test__output__exceptions(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_discover_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__output__playlist_created(
        self,
        mock_discover_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        playlist = PlaylistFactory.build()
        mock_discover_logic.return_value = playlist

        result = runner.invoke(app, ["spotify", "discover", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert f"Suggested tracks successfully saved into playlist {playlist.name}!" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_auth_token_repository",
    "mock_track_repository",
    "mock_spotify_client",
    "mock_advisor_client",
)
class TestSpotifyDiscoverLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.spotify.discover"

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        email = "test@example.com"
        with pytest.raises(UserNotFound):
            await discover_logic(email, advisor=MusicAdvisor.LASTFM, config=DiscoveryConfigInput())

    async def test__auth_token__not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError):
            await discover_logic(user.email, advisor=MusicAdvisor.LASTFM, config=DiscoveryConfigInput())
