from museflow.domain.entities.user import User
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats.artists import stats_artists_logic

from tests.integration.factories.models.track import TrackModelFactory


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

        result = await stats_artists_logic(
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
