from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.blacklist.export import blacklist_export_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.import_ import blacklist_import_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import blacklist_list_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.purge import blacklist_purge_logic

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestBlacklistImportLogic:
    async def test__nominal(self, user: User) -> None:
        data = {
            "artists": [{"artist_name": "Some Artist"}],
            "tracks": [{"name": "Some Track", "artist_name": "Another Artist"}],
        }

        result = await blacklist_import_logic(email=user.email, data=data)

        assert result.imported_artists_count == 1
        assert result.imported_tracks_count == 1
        assert result.skipped_count == 0

        blacklist = await blacklist_list_logic(email=user.email)
        assert blacklist.artist_names == ["Some Artist"]
        assert blacklist.track_display_strings == ["Some Track by Another Artist"]

    async def test__export__purge__import(self, user: User) -> None:
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedTrackModelFactory.create_async(user_id=user.id)
        before = await blacklist_list_logic(email=user.email)
        exported = await blacklist_export_logic(email=user.email)

        await blacklist_purge_logic(email=user.email)
        await blacklist_import_logic(email=user.email, data=exported.model_dump())

        after = await blacklist_list_logic(email=user.email)
        assert after.artist_names == before.artist_names
        assert after.track_display_strings == before.track_display_strings
