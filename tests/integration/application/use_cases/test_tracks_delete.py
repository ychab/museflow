from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.tracks_delete import delete_tracks
from museflow.application.use_cases.tracks_delete import find_tracks_to_delete
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider

from tests.integration.factories.models.track import TrackModelFactory


class TestFindTracksToDeleteUseCase:
    async def test__by_artist_and_name(self, uow: UnitOfWorkPort, user: User) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")

        tracks = await find_tracks_to_delete(
            user_id=user.id,
            artist="Radiohead",
            name="Creep",
            source=None,
            provider=None,
            uow=uow,
        )

        assert [track.id for track in tracks] == [creep_db.id]


class TestDeleteTracksUseCase:
    async def test__by_artist_and_name(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")

        deleted = await delete_tracks(
            user_id=user.id,
            artist="Radiohead",
            name="Creep",
            source=None,
            provider=None,
            uow=uow,
        )

        assert deleted == 1
        remaining = await find_tracks_to_delete(
            user_id=user.id,
            artist=None,
            name=None,
            source=None,
            provider=None,
            uow=uow,
        )
        assert [track.name for track in remaining] == ["Karma Police"]

    async def test__purge(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_batch_async(size=5, user_id=user.id)

        deleted = await delete_tracks(user_id=user.id, artist=None, name=None, source=None, provider=None, uow=uow)

        assert deleted == 5

    async def test__by_provider(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])

        deleted = await delete_tracks(
            user_id=user.id,
            artist=None,
            name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
            uow=uow,
        )

        assert deleted == 1
