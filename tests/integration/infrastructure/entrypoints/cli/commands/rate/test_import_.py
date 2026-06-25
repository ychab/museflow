from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.rate.import_ import import_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateImportLogic:
    async def test__nominal(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        data = [{"fingerprint": track_db.fingerprint, "score": 9}]

        result = await import_logic(email=user.email, data=data)

        assert result.imported_count == 1
        assert result.not_found_count == 0

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 9

    async def test__reimport_overrides(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=3)

        await import_logic(email=user.email, data=[{"fingerprint": track_db.fingerprint, "score": 9}])
        await import_logic(email=user.email, data=[{"fingerprint": track_db.fingerprint, "score": 5}])

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 5
