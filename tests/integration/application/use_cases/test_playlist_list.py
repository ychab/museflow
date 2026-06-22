from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.use_cases.playlist_list import playlist_list
from museflow.domain.entities.user import User

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistListUseCase:
    async def test__empty(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        result = await playlist_list(user=user, playlist_repository=playlist_repository)

        assert result == []

    async def test__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await playlist_list(user=user, playlist_repository=playlist_repository)

        ids = [playlist.id for playlist in result]
        assert playlist_db.id in ids
