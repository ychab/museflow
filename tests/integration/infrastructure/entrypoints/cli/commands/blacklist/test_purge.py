from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import blacklist_list_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.purge import blacklist_purge_logic

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestBlacklistPurgeLogic:
    async def test__nominal(self, user: User) -> None:
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        count = await blacklist_purge_logic(email=user.email)

        assert count == 2
        result = await blacklist_list_logic(email=user.email)
        assert result.is_empty

    async def test__empty(self, user: User) -> None:
        count = await blacklist_purge_logic(email=user.email)
        assert count == 0
