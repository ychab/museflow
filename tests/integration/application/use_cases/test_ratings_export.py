from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.ratings_export import export_ratings
from museflow.domain.entities.user import User

from tests.integration.factories.models.track import TrackModelFactory


class TestExportRatingsUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=7, score_skipped=False)
        skipped_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=True)
        await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)

        result = await export_ratings(user_id=user.id, uow=uow)

        assert [track.id for track in result.rated] == [rated_db.id]
        assert [track.id for track in result.skipped] == [skipped_db.id]
