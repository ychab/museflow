from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.discover.list_ import list_logic

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory


class TestListLogic:
    async def test__nominal(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)

        playlists = await discovery_playlist_repository.list(user.id)
        assert len(playlists) == 2

        await list_logic(email=user.email)
