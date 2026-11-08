from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.rate.export import rate_export_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateExportLogic:
    async def test__nominal(self, user: User) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=7)
        await TrackModelFactory.create_async(user_id=user.id, score=None)

        result = await rate_export_logic(email=user.email)

        assert result == [
            {
                "fingerprint": rated_db.fingerprint,
                "name": rated_db.name,
                "artists": rated_db.artists,
                "album_name": rated_db.album_name,
                "source": rated_db.source,
                "provider_links": rated_db.provider_links,
                "score": 7,
            }
        ]
