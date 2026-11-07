from museflow.application.inputs.blacklist import BlacklistArtistEntryInput
from museflow.application.inputs.blacklist import BlacklistImportInput
from museflow.application.inputs.blacklist import BlacklistTrackEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.blacklist_import import import_blacklist
from museflow.domain.entities.user import User
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestImportBlacklistUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort) -> None:
        await BlacklistedArtistModelFactory.create_async(
            user_id=user.id,
            artist_name="Known Artist",
            fingerprint=normalize_text("Known Artist"),
        )
        await BlacklistedTrackModelFactory.create_async(
            user_id=user.id,
            name="Known Track",
            artist_name="Known Artist",
            fingerprint=generate_fingerprint("Known Track", ["Known Artist"]),
        )
        blacklist_in = BlacklistImportInput(
            artists=[
                BlacklistArtistEntryInput(artist_name="KNOWN ARTIST"),
                BlacklistArtistEntryInput(artist_name="New Artist"),
                BlacklistArtistEntryInput(artist_name="new artist"),
            ],
            tracks=[
                BlacklistTrackEntryInput(name="known track", artist_name="known artist"),
                BlacklistTrackEntryInput(name="New Track", artist_name="New Artist"),
            ],
        )

        result = await import_blacklist(user_id=user.id, blacklist_in=blacklist_in, uow=uow)

        assert result.imported_artists_count == 1
        assert result.imported_tracks_count == 1
        assert result.skipped_count == 3

        async with uow:
            blacklist = await uow.blacklist.get(user_id=user.id)
        assert sorted(blacklist.artist_names) == ["Known Artist", "New Artist"]
        assert sorted(blacklist.track_display_strings) == ["Known Track by Known Artist", "New Track by New Artist"]
