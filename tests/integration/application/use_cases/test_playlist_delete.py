from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.use_cases.playlist_delete import playlist_delete
from museflow.domain.entities.user import User
from museflow.domain.types import PlaylistType

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistDeleteUseCase:
    async def test__single_delete__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_delete(user=user, playlist_repository=playlist_repository, playlist_id=playlist_db.id)

        assert count == 1
        assert await playlist_repository.get(user.id, playlist_db.id) is None

    async def test__purge__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id)
        await PlaylistModelFactory.create_async(user_id=user.id)

        count = await playlist_delete(user=user, playlist_repository=playlist_repository, purge=True)

        assert count == 2
        assert await playlist_repository.list(user.id) == []

    async def test__purge__filtered_by_type(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        count = await playlist_delete(
            user=user, playlist_repository=playlist_repository, purge=True, type=PlaylistType.DISCOVERY
        )

        assert count == 1
        assert await playlist_repository.get(user.id, playlist_db.id) is None
