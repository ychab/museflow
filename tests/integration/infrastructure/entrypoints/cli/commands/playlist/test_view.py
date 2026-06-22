from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.playlist.view import view_logic

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.track import TrackModelFactory


class TestViewLogic:
    async def test__nominal(self, user: User) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[track_db.id])

        await view_logic(email=user.email, playlist_id=playlist_db.id)
