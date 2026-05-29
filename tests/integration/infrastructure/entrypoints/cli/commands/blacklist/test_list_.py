from museflow.domain.entities.user import User
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import list_logic

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestListLogic:
    async def test__empty(self, user: User) -> None:
        result = await list_logic(email=user.email)
        assert isinstance(result, UserBlacklist)
        assert result.is_empty

    async def test__with_entries(self, user: User) -> None:
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        result = await list_logic(email=user.email)
        assert len(result.artists) == 1
        assert len(result.tracks) == 1
