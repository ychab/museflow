import math
from unittest import mock

import pytest

from museflow.application.use_cases.stats_artists import get_top_artists
from museflow.domain.entities.user import User
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource

from tests.unit.factories.value_objects.stats import ArtistTallyFactory


class TestGetTopArtistsUseCase:
    async def test__arguments_forwarded_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = []

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.HISTORY,
            score_min=3,
            score_max=8,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert result == []
        mock_track_repository.get_artist_tallies.assert_awaited_once_with(
            user_id=user.id, source=TrackSource.HISTORY, score_min=3, score_max=8
        )

    async def test__unrated_artists_included__ranked_by_volume(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 5 unrated tracks. Artist B: 1 track rated 8.
        # Volume first: Artist A (quality_ratio=1.0) outranks Artist B.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=5, plays_count=5, rated_count=0, rated_sum=0),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=8),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist A", "Artist B"]
        assert result[0].rate_avg is None
        assert result[0].quality_score is None

    async def test__global_mean__over_every_artist(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 10 tracks at 7. Artist B: 1 track at 10. global_mean = (70 + 10) / 11.
        # Quality sort ignores volume: B's smoothed quality, pulled toward the mean, still beats A's.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=10, plays_count=10, rated_count=10, rated_sum=70),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=10),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.QUALITY,
            uow=mock_uow,
        )

        global_mean = (70 + 10) / 11
        assert result[0].artist == "Artist B"
        assert result[0].quality_score == pytest.approx((5 * global_mean + 10) / 6)
        assert result[1].quality_score == pytest.approx((5 * global_mean + 70) / 15)

    async def test__sort_by_overall_promotes_volume(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 20 tracks at 7. Artist B: 1 track at 10: A's volume outweighs B's quality.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=20, plays_count=20, rated_count=20, rated_sum=140),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=10),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist A", "Artist B"]
        assert result[0].overall_score > result[1].overall_score

    async def test__no_rated_tracks__neutral_quality_ratio(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # No rating in range: global_mean = 0, the artist is ranked by volume alone.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=1, plays_count=1, rated_count=0, rated_sum=0),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 1
        assert result[0].rate_avg is None
        assert result[0].overall_score == pytest.approx(math.log(2) ** 2)

    async def test__tiebreaker_by_artist_name(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Zara", track_count=1, plays_count=1, rated_count=1, rated_sum=8),
            ArtistTallyFactory.build(artist="Aaron", track_count=1, plays_count=1, rated_count=1, rated_sum=8),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Aaron", "Zara"]

    async def test__limit_applied(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist 1", track_count=1, plays_count=1, rated_count=1, rated_sum=1),
            ArtistTallyFactory.build(artist="Artist 2", track_count=1, plays_count=1, rated_count=1, rated_sum=2),
            ArtistTallyFactory.build(artist="Artist 3", track_count=1, plays_count=1, rated_count=1, rated_sum=3),
            ArtistTallyFactory.build(artist="Artist 4", track_count=1, plays_count=1, rated_count=1, rated_sum=4),
            ArtistTallyFactory.build(artist="Artist 5", track_count=1, plays_count=1, rated_count=1, rated_sum=5),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=3,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 3

    async def test__sort_by_track_count(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist B (3 tracks) ranks first despite a lower average.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=1, plays_count=1, rated_count=1, rated_sum=9),
            ArtistTallyFactory.build(artist="Artist B", track_count=3, plays_count=3, rated_count=3, rated_sum=15),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.TRACK_COUNT,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist B", "Artist A"]

    async def test__sort_by_rate_avg(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist B (avg 10) ranks first despite fewer tracks.
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=10, plays_count=10, rated_count=10, rated_sum=60),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=10),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.RATE_AVG,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist B", "Artist A"]

    async def test__sort_by_rate_avg__unrated_at_bottom(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=10, plays_count=10, rated_count=0, rated_sum=0),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=5),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.RATE_AVG,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist B", "Artist A"]
        assert result[1].rate_avg is None

    async def test__sort_by_quality__unrated_at_bottom(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_artist_tallies.return_value = [
            ArtistTallyFactory.build(artist="Artist A", track_count=10, plays_count=10, rated_count=0, rated_sum=0),
            ArtistTallyFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=5),
        ]

        result = await get_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.QUALITY,
            uow=mock_uow,
        )

        assert [r.artist for r in result] == ["Artist B", "Artist A"]
        assert result[1].quality_score is None
