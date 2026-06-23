from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.playlist.history import playlist_history_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.history"


class TestHistoryParserCommand:
    @pytest.fixture(autouse=True)
    def mock_history_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_history_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = PlaylistFactory.build(tracks=[])
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "notanemail"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    def test__provider__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--provider", "foo"])
        assert result.exit_code != 0
        assert "Invalid value for '--provider'" in clean_typer_text(result.output)

    @pytest.mark.parametrize(
        ("score_min", "expected_msg"),
        [
            pytest.param(-1, "Invalid value for '--score-min': -1 is not in the range", id="below_min"),
            pytest.param(11, "Invalid value for '--score-min': 11 is not in the range", id="above_max"),
        ],
    )
    def test__score_min__out_of_range(
        self,
        runner: CliRunner,
        score_min: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--score-min", score_min])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)

    @pytest.mark.parametrize(
        ("score_max", "expected_msg"),
        [
            pytest.param(-1, "Invalid value for '--score-max': -1 is not in the range", id="below_min"),
            pytest.param(11, "Invalid value for '--score-max': 11 is not in the range", id="above_max"),
        ],
    )
    def test__score_max__out_of_range(
        self,
        runner: CliRunner,
        score_max: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--score-max", score_max])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)

    def test__limit__below_min(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--limit", "0"])
        assert result.exit_code != 0
        assert "Invalid value for '--limit': 0 is not in the range" in clean_typer_text(result.output)

    def test__score_min_greater_than_score_max__fails(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["playlist", "history", "--email", "test@example.com", "--score-min", "8", "--score-max", "2"],
        )
        assert result.exit_code != 0
        assert "--score-min cannot be greater than --score-max" in clean_typer_text(result.output)


class TestHistoryCommand:
    @pytest.fixture(autouse=True)
    def mock_history_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_history_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_history_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.stderr)

    def test__auth_token_not_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_history_logic.side_effect = ProviderAuthTokenNotFoundError()
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Auth token not found with email: test@example.com. Did you forget to connect?" in output

    def test__no_tracks_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_history_logic.side_effect = PlaylistNoTracksError()
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "No history tracks matched the given filters." in output

    def test__generic_exception(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_history_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)

    def test__output__playlist_created(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        track = TrackFactory.build(played_count=7)
        playlist = PlaylistFactory.build(name="History Playlist", tracks=[track])
        mock_history_logic.return_value = playlist

        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Successfully saved into playlist 'History Playlist'!" in output
        assert f"Saved playlist ID: {playlist.id}" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_auth_token_repository",
    "mock_track_repository",
    "mock_playlist_repository",
    "mock_provider_oauth",
)
class TestHistoryLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await playlist_history_logic(
                email="unknown@example.com",  # type: ignore[arg-type]
                provider=MusicProvider.SPOTIFY,
                config=PlaylistHistoryConfigInput(),
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
            await playlist_history_logic(
                email=user.email,  # type: ignore[arg-type]
                provider=MusicProvider.SPOTIFY,
                config=PlaylistHistoryConfigInput(),
            )
