from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.discover.view import view_logic

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory
from tests.integration.factories.models.discovery import DiscoveryPlaylistTrackModelFactory


class TestViewLogic:
    async def test__nominal(
        self,
        user: User,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
    ) -> None:
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id)
        await DiscoveryPlaylistTrackModelFactory.create_async(playlist_id=pl_db.id, position=0)

        await view_logic(email=user.email, playlist_id=pl_db.id)
