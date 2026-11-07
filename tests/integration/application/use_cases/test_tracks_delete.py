import uuid

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.tracks_delete import DeleteTracksUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory


class TestDeleteTracksUseCase:
    @pytest.fixture
    async def multi_linked_track_id(self, user: User, async_session_db: AsyncSession) -> uuid.UUID:
        # No second provider exists yet: a raw link stands for one. The entity can't load it, so the tests read it
        # back with SQL, not with `find`.
        track_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Massive Attack"])
        provider_links = [*track_db.provider_links, {"provider": "other", "provider_id": "other-id"}]
        await async_session_db.execute(
            update(TrackModel).where(TrackModel.id == track_db.id).values(provider_links=provider_links)
        )
        return track_db.id

    async def test__find__by_artist_name_and_source(self, uow: UnitOfWorkPort, user: User) -> None:
        creep_db = await TrackModelFactory.create_async(
            user_id=user.id,
            artists=["Radiohead"],
            name="Creep",
            source=TrackSource.HISTORY,
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            artists=["Radiohead"],
            name="Creep",
            source=TrackSource.DISCOVERY,
        )
        await TrackModelFactory.create_async(
            user_id=user.id,
            artists=["Radiohead"],
            name="Karma Police",
            source=TrackSource.HISTORY,
        )
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find(artist="Radiohead", name="Creep", source=TrackSource.HISTORY)

        assert [track.id for track in tracks] == [creep_db.id]

    async def test__delete__by_ids(self, uow: UnitOfWorkPort, user: User) -> None:
        creep_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Creep")
        await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"], name="Karma Police")
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        deleted = await use_case.delete(track_ids=[creep_db.id])

        assert deleted == 1
        remaining = await use_case.find(artist=None, name=None, source=None)
        assert [track.name for track in remaining] == ["Karma Police"]

    async def test__delete__by_provider__keeps_the_other_filters(
        self,
        uow: UnitOfWorkPort,
        user: User,
        async_session_db: AsyncSession,
        multi_linked_track_id: uuid.UUID,
    ) -> None:
        radiohead_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Radiohead"])
        portishead_db = await TrackModelFactory.create_async(user_id=user.id, artists=["Portishead"])
        use_case = DeleteTracksUseCase(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)
        tracks = await use_case.find(artist="Radiohead", name=None, source=None)

        deleted = await use_case.delete(track_ids=[track.id for track in tracks] + [multi_linked_track_id])

        # The track still linked to another provider is unlinked from Spotify, not deleted.
        assert deleted == 1
        stmt = select(TrackModel.id).where(TrackModel.user_id == user.id)
        remaining_ids = set((await async_session_db.execute(stmt)).scalars())
        assert remaining_ids == {portishead_db.id, multi_linked_track_id}
        assert radiohead_db.id not in remaining_ids

    async def test__purge__no_provider(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_batch_async(size=3, user_id=user.id)
        other_track_db = await TrackModelFactory.create_async()
        use_case = DeleteTracksUseCase(user_id=user.id, provider=None, uow=uow)

        deleted = await use_case.purge()

        assert deleted == 3
        async with uow:
            assert await uow.tracks.get_list(user_id=other_track_db.user_id) != []

    async def test__purge__by_provider(
        self,
        uow: UnitOfWorkPort,
        user: User,
        async_session_db: AsyncSession,
        multi_linked_track_id: uuid.UUID,
    ) -> None:
        await TrackModelFactory.create_batch_async(size=2, user_id=user.id)
        other_track_db = await TrackModelFactory.create_async()
        use_case = DeleteTracksUseCase(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)

        deleted = await use_case.purge()

        # The track still linked to another provider is unlinked from Spotify, not deleted.
        assert deleted == 2
        stmt = select(TrackModel.id).where(TrackModel.user_id == user.id)
        assert list((await async_session_db.execute(stmt)).scalars()) == [multi_linked_track_id]
        async with uow:
            assert await uow.tracks.get_list(user_id=other_track_db.user_id) != []
