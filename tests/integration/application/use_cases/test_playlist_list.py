from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_list import playlist_list
from museflow.domain.entities.user import User

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistListUseCase:
    async def test__empty(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        result = await playlist_list(user=user, uow=uow)

        assert result == []

    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await playlist_list(user=user, uow=uow)

        ids = [playlist.id for playlist in result]
        assert playlist_db.id in ids
