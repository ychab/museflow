from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.stats import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats.candidates import CandidateRow
from museflow.infrastructure.entrypoints.cli.commands.stats.candidates import candidates_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.music import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.candidates"


class TestStatsCandidatesParserCommand:
    @pytest.fixture(autouse=True)
    def mock_candidates_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.candidates_logic", new_callable=mock.AsyncMock) as patched:
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
    def mock_candidates_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.candidates_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_candidates(self, mock_candidates_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_candidates_logic.return_value = []
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No discovery candidates found." in result.output

    def test__with_candidates_table(self, mock_candidates_logic: mock.AsyncMock, runner: CliRunner) -> None:
        row = CandidateRow(artist="Artist X", avg_score=9.0, rated_count=1, total_count=2)
        mock_candidates_logic.return_value = [row]

        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])

        assert result.exit_code == 0
        assert "Discovery Candidates" in result.output
        assert "Artist X" in result.output
        assert "Avg Score" in result.output
        assert "Rated" in result.output
        assert "Total" in result.output

    def test__user_not_found(
        self,
        mock_candidates_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_candidates_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_candidates_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_candidates_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "candidates", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository")
class TestStatsCandidatesLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.candidates"

    async def test__nominal(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        candidate_track = TrackFactory.build(artists=["Hidden Gem"], score=9)
        popular_tracks = [TrackFactory.build(artists=["Big Name"], score=9) for _ in range(6)]
        low_score_track = TrackFactory.build(artists=["Mediocre"], score=4)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [candidate_track] + popular_tracks + [low_score_track]

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert len(result) == 1
        assert result[0].artist == "Hidden Gem"
        assert result[0].avg_score == 9.0
        assert result[0].rated_count == 1
        assert result[0].total_count == 1

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await candidates_logic(
                email="test@example.com",
                limit=20,
                source=SourceFilter.ALL,
                max_tracks=5,
                min_avg=7.0,
            )

    async def test__no_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result == []

    async def test__artist_with_too_many_tracks_excluded(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = [TrackFactory.build(artists=["Popular Artist"], score=9) for _ in range(6)]
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = tracks

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result == []

    async def test__artist_with_low_avg_excluded(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Mediocre Artist"], score=5)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track]

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result == []

    async def test__unrated_artist_excluded(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        unrated = TrackFactory.build(artists=["Unknown Artist"], score=None)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [unrated]

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result == []

    async def test__sorted_by_avg_score_desc(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_a = TrackFactory.build(artists=["Artist A"], score=8)
        track_b = TrackFactory.build(artists=["Artist B"], score=10)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_a, track_b]

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"

    async def test__tiebreaker_by_artist_name(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], score=9)
        track_a = TrackFactory.build(artists=["Aaron"], score=9)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await candidates_logic(email=user.email, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert result[0].artist == "Aaron"
        assert result[1].artist == "Zara"

    async def test__limit_applied(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = [TrackFactory.build(artists=[f"Artist {i}"], score=9) for i in range(5)]
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = tracks

        result = await candidates_logic(email=user.email, limit=3, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0)

        assert len(result) == 3
