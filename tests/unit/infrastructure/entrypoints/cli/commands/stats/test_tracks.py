from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.enums import TrackSortBy
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.stats.tracks import stats_tracks_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tracks"


class TestStatsTracksParserCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_tracks_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_tracks_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "tracks", "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__sort__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com", "--sort", "bogus"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--sort'" in output

    @pytest.mark.parametrize(
        ("option", "value"),
        [
            pytest.param("--score-min", "-1", id="score_min_below_range"),
            pytest.param("--score-min", "11", id="score_min_above_range"),
            pytest.param("--score-max", "-1", id="score_max_below_range"),
            pytest.param("--score-max", "11", id="score_max_above_range"),
        ],
    )
    def test__score__out_of_range(
        self, runner: CliRunner, option: str, value: str, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com", option, value])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert f"Invalid value for '{option}'" in output

    def test__score_min__greater_than_score_max(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["stats", "tracks", "--email", "test@example.com", "--score-min", "8", "--score-max", "3"],
        )
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "--score-min cannot be greater than --score-max" in output

    def test__limit__zero(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com", "--limit", "0"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--limit'" in output


class TestStatsTracksCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_tracks_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_tracks_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_rated_tracks(self, mock_stats_tracks_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_stats_tracks_logic.return_value = []
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No rated tracks found." in result.output

    def test__with_tracks_table(self, mock_stats_tracks_logic: mock.AsyncMock, runner: CliRunner) -> None:
        track = TrackFactory.build(name="Song A", artists=["Artist X"], score=9, played_count=42)
        mock_stats_tracks_logic.return_value = [track]

        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "Top Tracks" in result.output
        assert "Song A" in result.output
        assert "Artist(s)" in result.output
        assert "Played" in result.output
        assert "42" in result.output
        assert result.output.index("Artist(s)") < result.output.index("Song A")

    def test__user_not_found(
        self,
        mock_stats_tracks_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_tracks_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_stats_tracks_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_tracks_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestStatsTracksLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tracks"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await stats_tracks_logic(
                email="test@example.com", limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE
            )
