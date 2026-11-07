import math
from unittest import mock

import pytest

from museflow.application.use_cases.stats_artists import list_top_artists
from museflow.domain.entities.user import User
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource

from tests.unit.factories.entities.track import TrackFactory


class TestListTopArtistsUseCase:
    async def test__no_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert result == []

    async def test__unrated_artists_included__ranked_by_volume(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 5 unrated tracks. Artist B: 1 rated track (score=8).
        # Volume-first: Artist A (5 tracks, quality_ratio=1.0) outranks Artist B (1 track).
        # played_count pinned to 1 so the depth term doesn't add randomness to the comparison.
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=None, played_count=1) for _ in range(5)]
        track_b = TrackFactory.build(artists=["Artist B"], score=8, played_count=1)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 2
        artist_a = next(r for r in result if r.artist == "Artist A")
        assert artist_a.rate_avg is None
        assert artist_a.quality_score is None
        assert artist_a.rated_count == 0
        assert artist_a.track_count == 5
        assert result[0].artist == "Artist A"

    async def test__quality_score_pulls_low_count_toward_mean(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 10 tracks at 7. Artist B: 1 track at 10.
        # global_mean ≈ (10*7 + 10) / 11 ≈ 7.27
        # Artist B raw avg = 10, but smoothed quality pulls it toward mean → ≈7.73 (< 10)
        # quality sort is decoupled from volume: Artist B's smoothed quality is still higher
        # than Artist A's, so B ranks first here (unlike overall sort, which favors A's volume).
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=7) for _ in range(10)]
        track_b = TrackFactory.build(artists=["Artist B"], score=10)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.QUALITY,
            uow=mock_uow,
        )

        assert len(result) == 2
        artist_b = next(r for r in result if r.artist == "Artist B")
        global_mean = (10 * 7 + 10) / 11
        assert artist_b.quality_score is not None
        assert artist_b.rate_avg is not None
        # Artist B's quality score is between the global mean and their raw avg (pulled toward mean)
        assert global_mean < artist_b.quality_score < artist_b.rate_avg
        # Pure quality sort ignores volume entirely
        assert result[0].artist == "Artist B"

    async def test__sort_by_overall_promotes_volume(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 20 tracks at 7. Artist B: 1 track at 10.
        # overall = log(1 + track_count) × log(1 + plays_count) × (quality / global_mean)
        # played_count pinned to 1 so the depth term scales directly with track_count here.
        # Artist A: large volume → high overall despite modest quality_ratio.
        # Artist B: single track → low overall despite quality boost.
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=7, played_count=1) for _ in range(20)]
        track_b = TrackFactory.build(artists=["Artist B"], score=10, played_count=1)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist A"
        assert result[0].overall_score > result[1].overall_score

    async def test__aggregated_per_primary_artist(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_a1 = TrackFactory.build(artists=["Artist A", "Featured"], score=8)
        track_a2 = TrackFactory.build(artists=["Artist A"], score=6)
        track_b = TrackFactory.build(artists=["Artist B"], score=10)
        mock_track_repository.get_list.return_value = [track_a1, track_a2, track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 2
        artists = [r.artist for r in result]
        assert "Artist A" in artists
        assert "Artist B" in artists
        artist_a_row = next(r for r in result if r.artist == "Artist A")
        assert artist_a_row.rated_count == 2
        assert artist_a_row.track_count == 2
        assert artist_a_row.rate_avg == 7.0

    async def test__score_min_excludes_low_scored_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_high = TrackFactory.build(artists=["Artist A"], score=9)
        track_low = TrackFactory.build(artists=["Artist A"], score=3)
        mock_track_repository.get_list.return_value = [track_high, track_low]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=5,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 1
        assert result[0].rated_count == 1
        assert result[0].rate_avg == 9.0

    async def test__score_max_excludes_high_scored_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_high = TrackFactory.build(artists=["Artist A"], score=9)
        track_low = TrackFactory.build(artists=["Artist A"], score=3)
        mock_track_repository.get_list.return_value = [track_high, track_low]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=5,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 1
        assert result[0].rated_count == 1
        assert result[0].rate_avg == 3.0

    async def test__track_count_includes_unrated_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        rated = TrackFactory.build(artists=["Artist A"], score=8)
        unrated = TrackFactory.build(artists=["Artist A"], score=None)
        mock_track_repository.get_list.return_value = [rated, unrated]

        result = await list_top_artists(
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
        assert result[0].rated_count == 1
        assert result[0].track_count == 2

    async def test__plays_count_sums_played_count_across_artist_tracks(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        track_1 = TrackFactory.build(artists=["Artist A"], score=None, played_count=3)
        track_2 = TrackFactory.build(artists=["Artist A"], score=None, played_count=4)
        mock_track_repository.get_list.return_value = [track_1, track_2]

        result = await list_top_artists(
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
        assert result[0].plays_count == 7

    async def test__tiebreaker_by_artist_name(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # played_count pinned equal on both sides so the overall scores genuinely tie.
        track_z = TrackFactory.build(artists=["Zara"], score=8, played_count=1)
        track_a = TrackFactory.build(artists=["Aaron"], score=8, played_count=1)
        mock_track_repository.get_list.return_value = [track_z, track_a]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert result[0].artist == "Aaron"
        assert result[1].artist == "Zara"

    async def test__limit_applied(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        tracks = [TrackFactory.build(artists=[f"Artist {i}"], score=i) for i in range(1, 6)]
        mock_track_repository.get_list.return_value = tracks

        result = await list_top_artists(
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

    async def test__source_history_passed_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.HISTORY,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, source=TrackSource.HISTORY, limit=None
        )

    async def test__source_discovery_passed_to_repository(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.DISCOVERY,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=user.id, source=TrackSource.DISCOVERY, limit=None
        )

    async def test__fallback_global_mean_when_no_rated_tracks_in_range(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # All tracks filtered by score_min → global_mean = 0.0 → quality_ratio falls back to 1.0
        # Artist still appears ranked by volume alone.
        track = TrackFactory.build(artists=["Artist A"], score=3, played_count=1)
        mock_track_repository.get_list.return_value = [track]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=5,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
            uow=mock_uow,
        )

        assert len(result) == 1
        assert result[0].artist == "Artist A"
        assert result[0].rate_avg is None
        assert result[0].rated_count == 0
        assert result[0].overall_score == pytest.approx(math.log(2) ** 2)

    async def test__sort_by_track_count(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 1 rated track at 9. Artist B: 3 rated tracks at 5.
        # track_count sort → Artist B (3 tracks) ranks first despite lower avg score.
        track_a = TrackFactory.build(artists=["Artist A"], score=9)
        tracks_b = [TrackFactory.build(artists=["Artist B"], score=5) for _ in range(3)]
        mock_track_repository.get_list.return_value = [track_a] + tracks_b

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.TRACK_COUNT,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"

    async def test__sort_by_plays_count(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 1 track played 100 times. Artist B: 5 tracks played once each (5 plays total).
        # plays_count sort → Artist A ranks first despite having far fewer distinct tracks.
        track_a = TrackFactory.build(artists=["Artist A"], score=None, played_count=100)
        tracks_b = [TrackFactory.build(artists=["Artist B"], score=None, played_count=1) for _ in range(5)]
        mock_track_repository.get_list.return_value = [track_a] + tracks_b

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.PLAYS_COUNT,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist A"
        assert result[0].plays_count == 100
        assert result[1].plays_count == 5

    async def test__sort_by_rate_avg(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Artist A: 10 tracks at 6. Artist B: 1 track at 10.
        # rate_avg sort → Artist B (avg=10) ranks first despite fewer tracks.
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=6) for _ in range(10)]
        track_b = TrackFactory.build(artists=["Artist B"], score=10)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.RATE_AVG,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"

    async def test__sort_by_rate_avg__unrated_at_bottom(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Unrated artists (rate_avg=None) sink to the bottom when sorting by rate_avg.
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=None) for _ in range(10)]
        track_b = TrackFactory.build(artists=["Artist B"], score=5)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.RATE_AVG,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"
        assert result[1].rate_avg is None

    async def test__sort_by_quality__unrated_at_bottom(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        # Unrated artists (quality_score=None) sink to the bottom when sorting by quality.
        tracks_a = [TrackFactory.build(artists=["Artist A"], score=None) for _ in range(10)]
        track_b = TrackFactory.build(artists=["Artist B"], score=5)
        mock_track_repository.get_list.return_value = tracks_a + [track_b]

        result = await list_top_artists(
            user_id=user.id,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.QUALITY,
            uow=mock_uow,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist B"
        assert result[1].artist == "Artist A"
        assert result[1].quality_score is None
