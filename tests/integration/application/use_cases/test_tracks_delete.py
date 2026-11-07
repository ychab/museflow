from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.tracks_delete import DeleteTracksUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider

from tests.integration.factories.models.track import TrackModelFactory


class TestDeleteTracksUseCase:
    async def test__find__by_artist_and_name(self, uow: UnitOfWorkPort, user: User) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find(artist="Radiohead", name="Creep", source=None)

        assert [track.id for track in tracks] == [creep_db.id]

    async def test__delete__by_ids(self, uow: UnitOfWorkPort, user: User) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        deleted = await use_case.delete(track_ids=[creep_db.id])

        assert deleted == 1
        remaining = await use_case.find(artist=None, name=None, source=None)
        assert [track.name for track in remaining] == ["Karma Police"]

    async def test__delete__by_provider__keeps_the_other_filters(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        await TrackModelFactory.create_async(user_id=user.id, artists=["Portishead"])
        use_case = DeleteTracksUseCase(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)
        tracks = await use_case.find(artist="Radiohead", name=None, source=None)

        deleted = await use_case.delete(track_ids=[track.id for track in tracks])

        assert deleted == 1
        remaining = await use_case.find(artist=None, name=None, source=None)
        assert [track.artists for track in remaining] == [["Portishead"]]

    async def test__purge__no_provider(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_batch_async(size=3, user_id=user.id)
        other_track_db = await TrackModelFactory.create_async()
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        deleted = await use_case.purge()

        assert deleted == 3
        async with uow:
            assert await uow.tracks.get_list(user_id=other_track_db.user_id) != []

    async def test__purge__by_provider(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_batch_async(size=2, user_id=user.id)
        other_track_db = await TrackModelFactory.create_async()
        use_case = DeleteTracksUseCase(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)

        deleted = await use_case.purge()

        assert deleted == 2
        async with uow:
            assert await uow.tracks.get_list(user_id=user.id) == []
            assert await uow.tracks.get_list(user_id=other_track_db.user_id) != []
