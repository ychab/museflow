from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_view import get_playlist
from museflow.domain.entities.user import User

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestGetPlaylistUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        result = await get_playlist(
            user=user,
            playlist_id=playlist_db.id,
            uow=uow,
        )

        assert result.id == playlist_db.id
        assert result.name == playlist_db.name

    async def test__without_tracks(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[])

        result = await get_playlist(
            user=user,
            playlist_id=playlist_db.id,
            uow=uow,
        )

        assert result.id == playlist_db.id
        assert result.tracks == []
