from unittest import mock

from museflow.application.use_cases.stats_candidates import get_artist_candidates
from museflow.domain.entities.user import User
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource

from tests.unit.factories.value_objects.stats import ArtistTallyFactory


class TestGetArtistCandidatesUseCase:
    async def test__arguments_forwarded_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = []

        result = await get_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.DISCOVERY, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []
        mock_track_repository.get_artist_tallies.assert_awaited_once_with(
            user_id=user.id, source=TrackSource.DISCOVERY
        )

    async def test__unrated_artist_excluded(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Unknown Artist", rated_count=0, rated_sum=0),
        ]

        result = await get_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert result == []

    async def test__sorted_by_avg_score_desc(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", rated_count=1, rated_sum=8),
            ArtistTallyFactory.build(artist="Artist B", rated_count=1, rated_sum=10),
        ]

        result = await get_artist_candidates(
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
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Zara", rated_count=1, rated_sum=9),
            ArtistTallyFactory.build(artist="Aaron", rated_count=1, rated_sum=9),
        ]

        result = await get_artist_candidates(
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
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist=f"Artist {i}", rated_count=1, rated_sum=9) for i in range(5)
        ]

        result = await get_artist_candidates(
            user_id=user.id, limit=3, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=mock_uow
        )

        assert len(result) == 3
