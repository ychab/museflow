import math
from unittest import mock

import pytest

from museflow.application.use_cases.stats_artists import get_top_artists
from museflow.domain.entities.user import User
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource

from tests.unit.factories.value_objects.stats import ArtistStatsFactory


class TestGetTopArtistsUseCase:
    async def test__arguments_forwarded_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_stats.return_value = []

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.HISTORY,
            score_min=3,
            score_max=8,
            confidence=5,
            sort=RankingSortBy.OVERALL,
            uow=mock_uow,
        )

        assert result == []
        mock_track_repository.get_artist_stats.assert_awaited_once_with(
            user_id=user.id, source=TrackSource.HISTORY, score_min=3, score_max=8
        )

    async def test__global_mean__over_every_artist(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 10 tracks at 7. Artist B: 1 track at 10. global_mean = (70 + 10) / 11.
        # Quality sort ignores volume: B's smoothed quality, pulled toward the mean, still beats A's.
        mock_track_repository.get_artist_stats.return_value = [
            ArtistStatsFactory.build(artist="Artist A", track_count=10, plays_count=10, rated_count=10, rated_sum=70),
            ArtistStatsFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=10),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=RankingSortBy.QUALITY,
            uow=mock_uow,
        )

        global_mean = (70 + 10) / 11
        assert result[0].stats.artist == "Artist B"
        assert result[0].quality_score == pytest.approx((5 * global_mean + 10) / 6)
        assert result[1].quality_score == pytest.approx((5 * global_mean + 70) / 15)

    async def test__no_rated_tracks__neutral_quality_ratio(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # No rating in range: global_mean = 0, the artist is ranked by volume alone.
        mock_track_repository.get_artist_stats.return_value = [
            ArtistStatsFactory.build(artist="Artist A", track_count=1, plays_count=1, rated_count=0, rated_sum=0),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=RankingSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 1
        assert result[0].rate_avg is None
        assert result[0].overall_score == pytest.approx(math.log(2) ** 2)
