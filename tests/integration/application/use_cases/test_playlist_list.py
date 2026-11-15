from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_list import get_playlists
from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestGetPlaylistsUseCase:
    async def test__empty(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        result = await get_playlists(user=user, uow=uow)

        assert result == []

    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await get_playlists(user=user, uow=uow)

        ids = [playlist.id for playlist in result]
        assert playlist_db.id in ids

    async def test__type(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        explore_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.EXPLORE)
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        result = await get_playlists(user=user, uow=uow, type=PlaylistType.EXPLORE)

        assert [playlist.id for playlist in result] == [explore_db.id]
