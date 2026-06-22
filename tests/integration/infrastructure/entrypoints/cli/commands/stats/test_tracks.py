from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.stats.tracks import tracks_logic
from museflow.infrastructure.entrypoints.cli.types import TrackSortBy

from tests.integration.factories.models.track import TrackModelFactory


class TestStatsTracksLogic:
    async def test__nominal(self, user: User) -> None:
        track_a = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8)
        track_b = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=6)
        track_c = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=10)

        result = await tracks_logic(email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE)

        assert len(result) == 3
        # Tracks ordered by score DESC
        assert result[0].id == track_c.id
        assert result[1].id == track_a.id
        assert result[2].id == track_b.id

    async def test__sorted_by_played_count(self, user: User) -> None:
        track_a = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8, played_count=1)
        track_b = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=6, played_count=20)
        track_c = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=10, played_count=5)

        result = await tracks_logic(
            email=user.email, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT
        )

        assert len(result) == 3
        # Tracks ordered by played_count DESC
        assert result[0].id == track_b.id
        assert result[1].id == track_c.id
        assert result[2].id == track_a.id
