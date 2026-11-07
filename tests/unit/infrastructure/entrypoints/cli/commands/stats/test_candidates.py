from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFound
from museflow.domain.value_objects.stats import ArtistCandidate
from museflow.infrastructure.entrypoints.cli.commands.stats.candidates import stats_candidates_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.candidates"


class TestStatsCandidatesParserCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_candidates_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_candidates_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "candidates", "--email", "notanemail"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output

    def test__source__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com", "--source", "invalid"])
        assert result.exit_code != 0


class TestStatsCandidatesCommand:
    @pytest.fixture(autouse=True)
    def mock_stats_candidates_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.stats_candidates_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_candidates(self, mock_stats_candidates_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_stats_candidates_logic.return_value = []
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No discovery candidates found." in result.output

    def test__with_candidates_table(self, mock_stats_candidates_logic: mock.AsyncMock, runner: CliRunner) -> None:
        row = ArtistCandidate(artist="Artist X", avg_score=9.0, rated_count=1, total_count=2)
        mock_stats_candidates_logic.return_value = [row]

        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "Discovery Candidates" in result.output
        assert "Artist X" in result.output
        assert "Avg Score" in result.output
        assert "Rated" in result.output
        assert "Total" in result.output

    def test__user_not_found(
        self,
        mock_stats_candidates_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_candidates_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_stats_candidates_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_stats_candidates_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_unit_of_work")
class TestStatsCandidatesLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.candidates"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await stats_candidates_logic(
                email="test@example.com",
                limit=20,
                source=SourceFilter.ALL,
                max_tracks=5,
                min_avg=7.0,
            )
