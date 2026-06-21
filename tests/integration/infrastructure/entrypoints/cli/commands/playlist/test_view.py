from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.playlist.view import view_logic

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory
from tests.integration.factories.models.music import TrackModelFactory


class TestViewLogic:
    async def test__nominal(self, user: User) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id, track_ids=[track_db.id])

        await view_logic(email=user.email, playlist_id=pl_db.id)
