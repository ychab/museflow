from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.stats import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats.artists import ArtistSortBy
from museflow.infrastructure.entrypoints.cli.commands.stats.artists import artists_logic

from tests.integration.factories.models.music import TrackModelFactory


class TestStatsArtistsLogic:
    async def test__nominal(self, user: User) -> None:
        # Artist A: 2 rated tracks (avg=7.0), Artist B: 1 rated track (avg=10.0)
        # played_count pinned to 1 per track, so plays_count == track_count here.
        # With confidence=5, global_mean=(8+6+10)/3=8.0
        # Quality: Artist A = (5*8 + 2*7) / (5+2) = 54/7 ≈ 7.71, quality_ratio ≈ 0.964
        # Quality: Artist B = (5*8 + 1*10) / (5+1) = 50/6 ≈ 8.33, quality_ratio ≈ 1.042
        # Overall: Artist A ≈ log(3)² × 0.964 ≈ 1.16, Artist B ≈ log(2)² × 1.042 ≈ 0.50
        # → Artist A ranks first because volume outweighs quality advantage
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8, played_count=1)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=6, played_count=1)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=10, played_count=1)

        result = await artists_logic(
            email=user.email,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist A"
        assert result[0].rated_count == 2
        assert result[0].track_count == 2
        assert result[0].plays_count == 2
        assert result[1].artist == "Artist B"
        assert result[1].rated_count == 1
        assert result[1].track_count == 1
        assert result[1].plays_count == 1
        assert result[0].rate_avg == 7.0

    async def test__unrated_tracks_count_toward_total_but_not_rated(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=None)

        result = await artists_logic(
            email=user.email,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
        )

        assert len(result) == 1
        assert result[0].artist == "Artist A"
        assert result[0].rated_count == 1
        assert result[0].track_count == 2

    async def test__artist_with_only_unrated_tracks__included(self, user: User) -> None:
        # An artist with only unrated tracks appears ranked by volume alone (rate_avg=None).
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=None)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=None)

        result = await artists_logic(
            email=user.email,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.OVERALL,
        )

        assert len(result) == 1
        assert result[0].artist == "Artist A"
        assert result[0].rate_avg is None
        assert result[0].quality_score is None
        assert result[0].rated_count == 0
        assert result[0].track_count == 2

    async def test__sort_by_plays_count(self, user: User) -> None:
        # Artist A: 1 track with played_count=50. Artist B: 3 tracks with played_count=1 each.
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=None, played_count=50)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=None, played_count=1)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=None, played_count=1)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=None, played_count=1)

        result = await artists_logic(
            email=user.email,
            limit=20,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=ArtistSortBy.PLAYS_COUNT,
        )

        assert len(result) == 2
        assert result[0].artist == "Artist A"
        assert result[0].plays_count == 50
        assert result[1].artist == "Artist B"
        assert result[1].plays_count == 3
