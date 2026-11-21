from museflow.application.outputs.pagination import Page
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

        assert result == Page(items=[], total=0, limit=None, offset=0)

    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await get_playlists(user=user, uow=uow)

        assert [playlist.id for playlist in result.items] == [playlist_db.id]
        assert result.total == 1

    async def test__type(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        explore_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.EXPLORE)
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        result = await get_playlists(user=user, uow=uow, type=PlaylistType.EXPLORE)

        assert [playlist.id for playlist in result.items] == [explore_db.id]
        assert result.total == 1

    async def test__page(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlists_db = [await PlaylistModelFactory.create_async(user_id=user.id) for _ in range(3)]

        result = await get_playlists(user=user, uow=uow, limit=1, offset=1)

        # The newest first: the second page of one holds the middle playlist; the total counts every page
        assert [playlist.id for playlist in result.items] == [playlists_db[1].id]
        assert result.total == 3
        assert (result.limit, result.offset) == (1, 1)
