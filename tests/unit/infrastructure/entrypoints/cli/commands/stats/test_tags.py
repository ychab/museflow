from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.use_cases.stats_tags import GetTopTagsResult
from museflow.domain.enums import EnrichField
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.stats import Ranking
from museflow.infrastructure.entrypoints.cli.commands.stats.tags import stats_tags_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.value_objects.stats import TagStatsFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tags"


class TestStatsTagsParserCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_tags_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_tags_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = GetTopTagsResult(rankings=[], unenriched_count=0)
            yield patched

    @pytest.mark.parametrize(
        ("option", "value"),
        [
            pytest.param("--by", "artist", id="by"),
            pytest.param("--tier", "nano", id="tier"),
            pytest.param("--sort", "bad_value", id="sort"),
            pytest.param("--score-min", "11", id="score_min"),
            pytest.param("--limit", "0", id="limit"),
        ],
    )
    def test__option__invalid(self, runner: CliRunner, option: str, value: str, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "tags", "--email", "test@example.com", option, value])
        assert result.exit_code != 0
        assert f"Invalid value for '{option}'" in clean_typer_text(result.output)

    def test__tier__not_genre(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app, ["stats", "tags", "--email", "test@example.com", "--by", "mood", "--tier", "macro"]
        )
        assert result.exit_code != 0
        assert "--tier only applies to --by genre" in clean_typer_text(result.output)

    def test__score_min__greater_than_score_max(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["stats", "tags", "--email", "test@example.com", "--score-min", "8", "--score-max", "3"],
        )
        assert result.exit_code != 0
        assert "--score-min cannot be greater than --score-max" in clean_typer_text(result.output)


class TestStatsTagsCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_tags_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_tags_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__with_tags_table(self, mock_stats_tags_logic: mock.AsyncMock, runner: CliRunner) -> None:
        ranking = Ranking(
            stats=TagStatsFactory.build(tag="post-rock", rated_count=3, track_count=5, plays_count=12),
            quality_score=8.2,
            overall_score=37.1,
            rate_avg=9.0,
        )
        mock_stats_tags_logic.return_value = GetTopTagsResult(rankings=[ranking], unenriched_count=4)

        result = runner.invoke(app, ["stats", "tags", "--email", "test@example.com", "--tier", "meso"])

        assert result.exit_code == 0
        assert "Top Genres (meso)" in result.output
        assert "post-rock" in result.output
        assert "37.1" in result.output
        assert "4 tracks without genre are not ranked." in result.output

    def test__no_tags(self, mock_stats_tags_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_stats_tags_logic.return_value = GetTopTagsResult(rankings=[], unenriched_count=0)

        result = runner.invoke(app, ["stats", "tags", "--email", "test@example.com", "--by", "locale"])

        assert result.exit_code == 0
        assert "No locale stats found." in result.output
        assert "not ranked" not in result.output

    def test__user_not_found(
        self,
        mock_stats_tags_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_tags_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["stats", "tags", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__generic_exception(
        self,
        mock_stats_tags_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_tags_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "tags", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestStatsTagsLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tags"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await stats_tags_logic(
                email="test@example.com",
                by=EnrichField.GENRE,
                tier=None,
                source=SourceFilter.ALL,
                score_min=None,
                score_max=None,
                confidence=5,
                sort=RankingSortBy.OVERALL,
                limit=20,
            )
