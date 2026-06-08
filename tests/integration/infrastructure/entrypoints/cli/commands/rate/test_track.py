from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.rate.track import rate_track_logic

from tests.integration.factories.models.music import TrackModelFactory


class TestRateTrackLogic:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)

        await rate_track_logic(track_id=track_db.id, score=8, email=user.email)

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 8
