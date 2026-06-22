from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.use_cases.playlist_view import playlist_view
from museflow.domain.entities.user import User

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistViewUseCase:
    async def test__nominal(
        self,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await playlist_view(
            user=user,
            playlist_id=playlist_db.id,
            playlist_repository=playlist_repository,
        )

        assert result.id == playlist_db.id
        assert result.name == playlist_db.name
