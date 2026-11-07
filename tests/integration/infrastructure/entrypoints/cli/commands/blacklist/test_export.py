from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.blacklist.export import blacklist_export_logic

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestBlacklistExportLogic:
    async def test__nominal(self, user: User) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        result = await blacklist_export_logic(email=user.email)

        assert result.model_dump() == {
            "artists": [{"artist_name": artist_db.artist_name}],
            "tracks": [{"name": track_db.name, "artist_name": track_db.artist_name}],
        }
