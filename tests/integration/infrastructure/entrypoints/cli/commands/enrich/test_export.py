from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.enrich.export import export_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestEnrichExportLogic:
    async def test__nominal(self, user: User) -> None:
        enriched_db = await TrackModelFactory.create_async(
            user_id=user.id, genres=["rock", "indie-rock"], moods=["energetic"]
        )
        await TrackModelFactory.create_async(user_id=user.id, genres=[])

        result = await export_logic(email=user.email)

        assert len(result) == 1
        assert result[0]["fingerprint"] == enriched_db.fingerprint
        assert result[0]["genres"] == ["rock", "indie-rock"]
        assert result[0]["moods"] == ["energetic"]
