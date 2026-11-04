import pytest

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.tracks_delete import TracksDeleteUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider

from tests.integration.factories.models.track import TrackModelFactory


class TestTracksDeleteUseCase:
    @pytest.fixture
    def use_case(self, uow: UnitOfWorkPort) -> TracksDeleteUseCase:
        return TracksDeleteUseCase(uow=uow)

    async def test__find__by_artist_and_name(
        self,
        use_case: TracksDeleteUseCase,
        user: User,
    ) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")

        tracks = await use_case.find(user_id=user.id, artist="Radiohead", name="Creep", source=None, provider=None)

        assert [track.id for track in tracks] == [creep_db.id]

    async def test__delete__by_ids(
        self,
        use_case: TracksDeleteUseCase,
        user: User,
    ) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")

        deleted = await use_case.delete(user_id=user.id, track_ids=[creep_db.id], provider=None)

        assert deleted == 1
        remaining = await use_case.find(user_id=user.id, artist=None, name=None, source=None, provider=None)
        assert [track.name for track in remaining] == ["Karma Police"]

    async def test__delete__by_provider__keeps_the_other_filters(
        self,
        use_case: TracksDeleteUseCase,
        user: User,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        await TrackModelFactory.create_async(user_id=user.id, artists=["Portishead"])
        tracks = await use_case.find(
            user_id=user.id,
            artist="Radiohead",
            name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
        )

        deleted = await use_case.delete(
            user_id=user.id,
            track_ids=[track.id for track in tracks],
            provider=MusicProvider.SPOTIFY,
        )

        assert deleted == 1
        remaining = await use_case.find(user_id=user.id, artist=None, name=None, source=None, provider=None)
        assert [track.artists for track in remaining] == [["Portishead"]]

    async def test__delete_all__nominal(
        self,
        use_case: TracksDeleteUseCase,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        await TrackModelFactory.create_batch_async(size=3, user_id=user.id)
        other_track_db = await TrackModelFactory.create_async()

        deleted = await use_case.delete_all(user_id=user.id)

        assert deleted == 3
        async with uow:
            assert await uow.tracks.get_list(user_id=other_track_db.user_id) != []
