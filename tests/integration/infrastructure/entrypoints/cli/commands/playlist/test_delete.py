from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.entrypoints.cli.commands.playlist.delete import playlist_delete_logic

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistDeleteLogic:
    async def test__single_delete__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_delete_logic(
            email=user.email, playlist_id=playlist_db.id, purge=False, type=None, provider=None
        )

        assert count == 1
        assert await playlist_repository.get(user.id, playlist_db.id) is None

    async def test__purge__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id)
        await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_delete_logic(email=user.email, playlist_id=None, purge=True, type=None, provider=None)

        assert count == 2
        assert await playlist_repository.get_list(user.id) == []

    async def test__purge__filtered(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(
            user_id=user.id,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )
        other_type_db = await PlaylistModelFactory.create_async(
            user_id=user.id,
            type=PlaylistType.HISTORY,
            provider=MusicProvider.SPOTIFY,
        )

        count = await playlist_delete_logic(
            email=user.email,
            playlist_id=None,
            purge=True,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )

        assert count == 1
        assert await playlist_repository.get(user.id, playlist_db.id) is None
        assert await playlist_repository.get(user.id, other_type_db.id) is not None
