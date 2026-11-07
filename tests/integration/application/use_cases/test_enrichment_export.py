from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.enrichment_export import export_enrichment
from museflow.domain.entities.user import User

from tests.integration.factories.models.track import TrackModelFactory


class TestExportEnrichmentUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort) -> None:
        enriched_db = await TrackModelFactory.create_async(
            user_id=user.id,
            genres=["rock"],
            moods=["energetic"],
            locales=["en"],
        )
        instrumental_db = await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[], locales=[])
        await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[], locales=None)

        result = await export_enrichment(user_id=user.id, uow=uow)

        assert {track.id for track in result} == {enriched_db.id, instrumental_db.id}
