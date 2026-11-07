from unittest import mock

from museflow.application.use_cases.stats_candidates import list_artist_candidates
from museflow.domain.entities.user import User
from museflow.domain.enums import SourceFilter

from tests.unit.factories.entities.track import TrackFactory


class TestListArtistCandidatesUseCase:
    async def test__nominal(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        candidate_track = TrackFactory.build(artists=["Hidden Gem"], score=9)
        popular_tracks = [TrackFactory.build(artists=["Big Name"], score=9) for _ in range(6)]
        low_score_track = TrackFactory.build(artists=["Mediocre"], score=4)
        mock_track_repository.get_list.return_value = [candidate_track] + popular_tracks + [low_score_track]

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert len(result) == 1
        assert result[0].artist == "Hidden Gem"
        assert result[0].avg_score == 9.0
        assert result[0].rated_count == 1
        assert result[0].total_count == 1

    async def test__no_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []

    async def test__artist_with_too_many_tracks_excluded(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = [TrackFactory.build(artists=["Popular Artist"], score=9) for _ in range(6)]
        mock_track_repository.get_list.return_value = tracks

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []

    async def test__artist_with_low_avg_excluded(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track = TrackFactory.build(artists=["Mediocre Artist"], score=5)
        mock_track_repository.get_list.return_value = [track]

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []

    async def test__unrated_artist_excluded(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        unrated = TrackFactory.build(artists=["Unknown Artist"], score=None)
        mock_track_repository.get_list.return_value = [unrated]

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []

    async def test__sorted_by_avg_score_desc(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_a = TrackFactory.build(artists=["Artist A"], score=8)
        track_b = TrackFactory.build(artists=["Artist B"], score=10)
        mock_track_repository.get_list.return_value = [track_a, track_b]

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"

    async def test__tiebreaker_by_artist_name(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_z = TrackFactory.build(artists=["Zara"], score=9)
        track_a = TrackFactory.build(artists=["Aaron"], score=9)
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await list_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result[0].artist == "Aaron"
        assert result[1].artist == "Zara"

    async def test__limit_applied(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = [TrackFactory.build(artists=[f"Artist {i}"], score=9) for i in range(5)]
        mock_track_repository.get_list.return_value = tracks

        result = await list_artist_candidates(
            user_id=user.id, limit=3, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert len(result) == 3
