from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.inputs.rate import RateEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.ratings_import import import_ratings
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory


class TestImportRatingsUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        skipped_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        entries = [
            RateEntryInput(fingerprint=rated_db.fingerprint, score=9),
            RateEntryInput(fingerprint=skipped_db.fingerprint, score_skipped=True),
            RateEntryInput(fingerprint="unknown-fp", score=5),
        ]

        result = await import_ratings(user_id=user.id, entries=entries, uow=uow)

        assert result.imported_count == 1
        assert result.skipped_count == 1
        assert result.not_found_count == 1

        stmt = select(TrackModel).where(TrackModel.id.in_([rated_db.id, skipped_db.id]))
        tracks_db = {track.id: track for track in (await async_session_db.execute(stmt)).scalars()}
        assert tracks_db[rated_db.id].score == 9
        assert tracks_db[skipped_db.id].score_skipped is True
