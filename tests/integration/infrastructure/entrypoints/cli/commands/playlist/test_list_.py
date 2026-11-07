from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.playlist.list_ import playlist_list_logic

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistListLogic:
    async def test__nominal(self, user: User) -> None:
        playlists_db = await PlaylistModelFactory.create_batch_async(size=2, user_id=user.id)
        await PlaylistModelFactory.create_async()

        playlists = await playlist_list_logic(email=user.email)

        assert {playlist.id for playlist in playlists} == {playlist_db.id for playlist_db in playlists_db}
