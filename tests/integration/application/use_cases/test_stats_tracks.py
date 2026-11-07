from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.stats_tracks import get_top_tracks
from museflow.domain.entities.user import User
from museflow.domain.enums import TrackSortBy

from tests.integration.factories.models.track import TrackModelFactory


class TestGetTopTracksUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        track_a = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8)
        track_b = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=6)
        track_c = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=10)
        # Without score_min, the minimum score defaults to 0: unrated tracks are left out.
        await TrackModelFactory.create_async(user_id=user.id, artists=["Artist C"], score=None)

        result = await get_top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.SCORE, uow=uow
        )

        assert len(result) == 3
        # Tracks ordered by score DESC
        assert result[0].id == track_c.id
        assert result[1].id == track_a.id
        assert result[2].id == track_b.id

    async def test__sorted_by_played_count(self, uow: UnitOfWorkPort, user: User) -> None:
        track_a = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=8, played_count=1)
        track_b = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist A"], score=6, played_count=20)
        track_c = await TrackModelFactory.create_async(user_id=user.id, artists=["Artist B"], score=10, played_count=5)

        result = await get_top_tracks(
            user_id=user.id, limit=20, score_min=None, score_max=None, sort=TrackSortBy.PLAYED_COUNT, uow=uow
        )

        assert len(result) == 3
        # Tracks ordered by played_count DESC
        assert result[0].id == track_b.id
        assert result[1].id == track_c.id
        assert result[2].id == track_a.id

    async def test__score_range(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, score=3)
        track_in_range = await TrackModelFactory.create_async(user_id=user.id, score=6)
        await TrackModelFactory.create_async(user_id=user.id, score=9)

        result = await get_top_tracks(
            user_id=user.id, limit=20, score_min=5, score_max=8, sort=TrackSortBy.SCORE, uow=uow
        )

        assert [track.id for track in result] == [track_in_range.id]
