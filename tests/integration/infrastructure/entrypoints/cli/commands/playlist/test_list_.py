from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.entrypoints.cli.commands.playlist.list_ import playlist_list_logic

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistListLogic:
    async def test__nominal(self, user: User) -> None:
        playlists_db = await PlaylistModelFactory.create_batch_async(size=2, user_id=user.id)
        await PlaylistModelFactory.create_async()

        playlists = await playlist_list_logic(email=user.email)

        assert {playlist.id for playlist in playlists} == {playlist_db.id for playlist_db in playlists_db}

    async def test__type(self, user: User) -> None:
        history_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.HISTORY)
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.EXPLORE)

        playlists = await playlist_list_logic(email=user.email, type=PlaylistType.HISTORY)

        assert [playlist.id for playlist in playlists] == [history_db.id]
