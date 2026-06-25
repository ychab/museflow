from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.rate.export import export_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateExportLogic:
    async def test__nominal(self, user: User) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=7)
        await TrackModelFactory.create_async(user_id=user.id, score=None)

        result = await export_logic(email=user.email)

        assert len(result) == 1
        assert result[0]["fingerprint"] == rated_db.fingerprint
        assert result[0]["score"] == 7
