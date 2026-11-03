from unittest import mock

from museflow.application.use_cases.stats_tracks import top_tracks
from museflow.domain.entities.user import User
from museflow.domain.enums import TrackSortBy

from tests.unit.factories.entities.track import TrackFactory


class TestTopTracksUseCase:
    async def test__no_rated_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow
        )

        assert result == []

    async def test__returns_tracks_sorted_by_score_desc(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], score=5)
        track_high = TrackFactory.build(artists=["Artist B"], score=9)
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow
        )

        assert result[0].score == 9
        assert result[1].score == 5

    async def test__tiebreaker_by_artist(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], score=8)
        track_a = TrackFactory.build(artists=["Aaron"], score=8)
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow
        )

        assert result[0].artists[0] == "Aaron"
        assert result[1].artists[0] == "Zara"

    async def test__returns_tracks_sorted_by_played_count_desc(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], played_count=2)
        track_high = TrackFactory.build(artists=["Artist B"], played_count=9)
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT, uow=mock_uow
        )

        assert result[0].played_count == 9
        assert result[1].played_count == 2

    async def test__tiebreaker_by_artist_when_sorted_by_played_count(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], played_count=4)
        track_a = TrackFactory.build(artists=["Aaron"], played_count=4)
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT, uow=mock_uow
        )

        assert result[0].artists[0] == "Aaron"
        assert result[1].artists[0] == "Zara"

    async def test__limit_applied_after_sorting(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_low = TrackFactory.build(artists=["Artist A"], score=5)
        track_high = TrackFactory.build(artists=["Artist B"], score=9)
        mock_track_repository.get_list.return_value = [track_low, track_high]

        result = await top_tracks(
            user_id=user.id, limit=1, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow
        )

        assert result == [track_high]

    async def test__score_min_passed_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await top_tracks(user_id=user.id, limit=20, score_min=7, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow)

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, min_score=7, max_score=None, limit=None
        )

    async def test__score_min_defaults_to_zero_when_none(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=mock_uow
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, min_score=0, max_score=None, limit=None
        )
