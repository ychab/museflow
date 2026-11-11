from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.stats import ArtistRanking
from museflow.infrastructure.entrypoints.cli.commands.stats.artists import stats_artists_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.artists"


class TestStatsArtistsParserCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_artists_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_artists_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "artists", "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__source__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com", "--source", "invalid"])
        assert result.exit_code != 0

    def test__sort__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com", "--sort", "bad_value"])
        assert result.exit_code != 0

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
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com", option, value])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert f"Invalid value for '{option}'" in output

    def test__score_min__greater_than_score_max(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["stats", "artists", "--email", "test@example.com", "--score-min", "8", "--score-max", "3"],
        )
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "--score-min cannot be greater than --score-max" in output

    def test__limit__zero(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com", "--limit", "0"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--limit'" in output


class TestStatsArtistsCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_artists_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_artists_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_artists(self, mock_stats_artists_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_stats_artists_logic.return_value = []
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No artist stats found." in result.output

    def test__with_artists_table(self, mock_stats_artists_logic: mock.AsyncMock, runner: CliRunner) -> None:
        row = ArtistRanking(
            artist="Artist X",
            quality_score=8.2,
            overall_score=37.1,
            rate_avg=9.0,
            rated_count=3,
            track_count=5,
            plays_count=12,
        )
        mock_stats_artists_logic.return_value = [row]

        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "Top Artists" in result.output
        assert "Artist X" in result.output
        assert "Quality" in result.output
        assert "Rate Avg" in result.output
        assert "Rated" in result.output
        assert "Tracks" in result.output
        assert "Played" in result.output
        assert "Overall" in result.output
        assert "37.1" in result.output

    def test__with_artists_table__rate_avg_sort(
        self, mock_stats_artists_logic: mock.AsyncMock, runner: CliRunner
    ) -> None:
        row = ArtistRanking(
            artist="Artist X",
            quality_score=8.2,
            overall_score=37.1,
            rate_avg=9.0,
            rated_count=3,
            track_count=5,
            plays_count=12,
        )
        mock_stats_artists_logic.return_value = [row]

        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com", "--sort", "rate_avg"])

        assert result.exit_code == 0
        assert "8.2" in result.output
        assert "Overall" not in result.output
        assert "37.1" not in result.output

    def test__with_unrated_artist(self, mock_stats_artists_logic: mock.AsyncMock, runner: CliRunner) -> None:
        row = ArtistRanking(
            artist="Unrated Artist",
            quality_score=None,
            overall_score=1.8,
            rate_avg=None,
            rated_count=0,
            track_count=5,
            plays_count=7,
        )
        mock_stats_artists_logic.return_value = [row]

        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "Unrated Artist" in result.output
        assert "—" in result.output

    def test__user_not_found(
        self,
        mock_stats_artists_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_artists_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_stats_artists_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_artists_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "artists", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestStatsArtistsLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.artists"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await stats_artists_logic(
                email="test@example.com",
                limit=20,
                source=SourceFilter.ALL,
                score_min=None,
                score_max=None,
                confidence=5,
                sort=ArtistSortBy.OVERALL,
            )
