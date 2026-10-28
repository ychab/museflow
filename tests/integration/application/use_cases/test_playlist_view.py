from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_view import playlist_view
from museflow.domain.entities.user import User

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistViewUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await playlist_view(
            user=user,
            playlist_id=playlist_db.id,
            uow=uow,
        )

        assert result.id == playlist_db.id
        assert result.name == playlist_db.name
