from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import list_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.remove import remove_logic

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestRemoveLogic:
    async def test__artist(self, user: User) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)

        await remove_logic(email=user.email, item_ids=[artist_db.id])

        result = await list_logic(email=user.email)
        assert result.is_empty

    async def test__track(self, user: User) -> None:
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        await remove_logic(email=user.email, item_ids=[track_db.id])

        result = await list_logic(email=user.email)
        assert result.is_empty

    async def test__multiple(self, user: User) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        await remove_logic(email=user.email, item_ids=[artist_db.id, track_db.id])

        result = await list_logic(email=user.email)
        assert result.is_empty
