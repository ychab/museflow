from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.inputs.enrich import EnrichEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.enrichment_import import import_enrichment
from museflow.domain.entities.user import User
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory


class TestImportEnrichmentUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[], locales=None)
        entries = [
            EnrichEntryInput(
                fingerprint=track_db.fingerprint,
                genres=[GenreTag.FOLK],
                moods=[MoodTag.MELANCHOLIC],
                locales=["fr"],
            ),
            EnrichEntryInput(fingerprint="unknown-fp", genres=[GenreTag.ROCK]),
        ]

        result = await import_enrichment(user_id=user.id, entries=entries, uow=uow)

        assert result.imported_count == 1
        assert result.not_found_count == 1

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.genres == ["folk"]
        assert updated.moods == ["melancholic"]
        assert updated.locales == ["fr"]
