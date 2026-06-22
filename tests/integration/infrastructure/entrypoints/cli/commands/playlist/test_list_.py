from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.playlist.list_ import list_logic

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestListLogic:
    async def test__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id)
        await PlaylistModelFactory.create_async(user_id=user.id)

        playlists = await playlist_repository.list(user.id)
        assert len(playlists) == 2

        await list_logic(email=user.email)
