from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.domain.entities.user import User
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
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

    def test__name_suffix__passed_to_config(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(
            app,
            ["playlist", "history", "--email", "test@example.com", "--name-suffix", "My Mix"],
        )
        assert result.exit_code == 0
        config = mock_history_logic.call_args.kwargs["config"]
        assert config.name_suffix == "My Mix"

    def test__genre__invalid__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--genre", "foobar"])
        assert result.exit_code != 0
        assert "Invalid value for '--genre'" in clean_typer_text(result.output)

    def test__mood__invalid__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--mood", "foobar"])
        assert result.exit_code != 0
        assert "Invalid value for '--mood'" in clean_typer_text(result.output)

    def test__genre__valid__passed_to_config(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--genre", "hip-hop"])
        assert result.exit_code == 0
        config = mock_history_logic.call_args.kwargs["config"]
        assert config.genres == [GenreTag.HIP_HOP]

    def test__mood__valid__passed_to_config(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--mood", "chill"])
        assert result.exit_code == 0
        config = mock_history_logic.call_args.kwargs["config"]
        assert config.moods == [MoodTag.CHILL]

    def test__multiple_genres__passed_to_config(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(
            app,
            ["playlist", "history", "--email", "test@example.com", "--genre", "hip-hop", "--genre", "rock"],
        )
        assert result.exit_code == 0
        config = mock_history_logic.call_args.kwargs["config"]
        assert config.genres == [GenreTag.HIP_HOP, GenreTag.ROCK]

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

    @pytest.mark.parametrize(
        ("flag", "value"),
        [
            pytest.param("--played-first-min", "notadate", id="played_first_min__bad_format"),
            pytest.param("--played-last-min", "2026/06/01", id="played_last_min__bad_format"),
        ],
    )
    def test__date_option__invalid_format__fails(
        self,
        runner: CliRunner,
        flag: str,
        value: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", flag, value])
        assert result.exit_code != 0
        assert "Date must be in YYYY-MM-DD format" in clean_typer_text(result.output)

    def test__played_first_min_after_max__fails(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "playlist",
                "history",
                "--email",
                "test@example.com",
                "--played-first-min",
                "2026-12-01",
                "--played-first-max",
                "2026-01-01",
            ],
        )
        assert result.exit_code != 0
        assert "--played-first-min cannot be after --played-first-max" in clean_typer_text(result.output)

    def test__played_last_min_after_max__fails(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "playlist",
                "history",
                "--email",
                "test@example.com",
                "--played-last-min",
                "2026-12-01",
                "--played-last-max",
                "2026-01-01",
            ],
        )
        assert result.exit_code != 0
        assert "--played-last-min cannot be after --played-last-max" in clean_typer_text(result.output)


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

    def test__output__score_column_shown(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        track_scored = TrackFactory.build(score=8)
        track_unscored = TrackFactory.build(score=None)
        playlist = PlaylistFactory.build(tracks=[track_scored, track_unscored])
        mock_history_logic.return_value = playlist

        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Score" in output
        assert "8" in output
        assert "-" in output

    def test__output__group_by_artists__header_shown(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        playlist = PlaylistFactory.build(tracks=[])
        mock_history_logic.return_value = playlist

        result = runner.invoke(app, ["playlist", "history", "--email", "test@example.com", "--group-by-artists"])
        assert result.exit_code == 0
        assert "Tracks are grouped by primary artist." in clean_typer_text(result.stdout)


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
