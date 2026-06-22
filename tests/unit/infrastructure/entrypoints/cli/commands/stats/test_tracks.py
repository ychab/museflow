from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.stats.tracks import tracks_logic
from museflow.infrastructure.entrypoints.cli.main import app
from museflow.infrastructure.entrypoints.cli.types import TrackSortBy

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tracks"


class TestStatsTracksParserCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.tracks_logic", new_callable=mock.AsyncMock) as patched:
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


class TestStatsTracksCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.tracks_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_rated_tracks(self, mock_tracks_logic: mock.AsyncMock, runner: CliRunner) -> None:
        mock_tracks_logic.return_value = []
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No rated tracks found." in result.output

    def test__with_tracks_table(self, mock_tracks_logic: mock.AsyncMock, runner: CliRunner) -> None:
        track = TrackFactory.build(name="Song A", artists=["Artist X"], score=9, played_count=42)
        mock_tracks_logic.return_value = [track]

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
        mock_tracks_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_tracks_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_tracks_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_tracks_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["stats", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository")
class TestStatsTracksLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.stats.tracks"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await tracks_logic(
                email="test@example.com", limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE
            )

    async def test__no_rated_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        result = await tracks_logic(email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        assert result == []

    async def test__returns_tracks_sorted_by_score_desc(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], score=5)
        track_high = TrackFactory.build(artists=["Artist B"], score=9)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await tracks_logic(email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        assert result[0].score == 9
        assert result[1].score == 5

    async def test__tiebreaker_by_artist(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], score=8)
        track_a = TrackFactory.build(artists=["Aaron"], score=8)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await tracks_logic(email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        assert result[0].artists[0] == "Aaron"
        assert result[1].artists[0] == "Zara"

    async def test__returns_tracks_sorted_by_played_count_desc(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], played_count=2)
        track_high = TrackFactory.build(artists=["Artist B"], played_count=9)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await tracks_logic(
            email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT
        )

        assert result[0].played_count == 9
        assert result[1].played_count == 2

    async def test__tiebreaker_by_artist_when_sorted_by_played_count(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], played_count=4)
        track_a = TrackFactory.build(artists=["Aaron"], played_count=4)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await tracks_logic(
            email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT
        )

        assert result[0].artists[0] == "Aaron"
        assert result[1].artists[0] == "Zara"

    async def test__limit_applied_after_sorting(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], score=5)
        track_high = TrackFactory.build(artists=["Artist B"], score=9)
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await tracks_logic(email=user.email, limit=1, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        assert result == [track_high]

    async def test__score_min_passed_to_repository(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        await tracks_logic(email=user.email, limit=20, score_min=7, score_max=None, sort=TrackSortBy.SCORE)

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, min_score=7, max_score=None, limit=None
        )

    async def test__score_min_defaults_to_zero_when_none(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        await tracks_logic(email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, min_score=0, max_score=None, limit=None
        )
