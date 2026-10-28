import uuid
from dataclasses import replace

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import QueuePool

import pytest

from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.track import Track as TrackModel
from museflow.infrastructure.adapters.database.session import async_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory


@pytest.mark.usefixtures("async_session_trans")
class TestSQLUnitOfWork:
    """Real commits (`async_session_trans`): the default test session runs each block in a savepoint."""

    @pytest.fixture
    def unit_of_work(self) -> SQLUnitOfWork:
        return SQLUnitOfWork(async_session_factory)

    @pytest.fixture
    def tracks(self, user: User) -> list[Track]:
        return TrackFactory.batch(size=2, user_id=user.id)

    @staticmethod
    async def count_rows(user_id: uuid.UUID) -> tuple[int, int]:
        # A separate session only sees committed rows.
        async with async_session_factory() as session:
            tracks_count = await session.scalar(
                select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user_id)
            )
            playlists_count = await session.scalar(
                select(func.count()).select_from(PlaylistModel).where(PlaylistModel.user_id == user_id)
            )
        return tracks_count or 0, playlists_count or 0

    async def test__clean_exit__commits_writes_together(
        self,
        unit_of_work: SQLUnitOfWork,
        user: User,
        tracks: list[Track],
    ) -> None:
        async with unit_of_work as uow:
            track_ids, _ = await uow.tracks.bulk_upsert(tracks, batch_size=100)
            assert await self.count_rows(user.id) == (0, 0)

            tracks_with_ids = [replace(t, id=track_ids[t.fingerprint]) for t in tracks]
            await uow.playlists.save(PlaylistFactory.build(user_id=user.id, profile_id=None, tracks=tracks_with_ids))
            assert await self.count_rows(user.id) == (0, 0)

        assert await self.count_rows(user.id) == (2, 1)

    async def test__exception__rolls_back(self, unit_of_work: SQLUnitOfWork, user: User, tracks: list[Track]) -> None:
        with pytest.raises(ValueError, match="boom"):
            async with unit_of_work as uow:
                await uow.tracks.bulk_upsert(tracks, batch_size=100)
                raise ValueError("boom")

        assert await self.count_rows(user.id) == (0, 0)

    async def test__rollback__discards_writes(
        self,
        unit_of_work: SQLUnitOfWork,
        user: User,
        tracks: list[Track],
    ) -> None:
        async with unit_of_work as uow:
            await uow.tracks.bulk_upsert(tracks, batch_size=100)
            await uow.rollback()

        assert await self.count_rows(user.id) == (0, 0)

    async def test__exit__returns_connection_to_pool(
        self,
        unit_of_work: SQLUnitOfWork,
        async_engine: AsyncEngine,
        user: User,
    ) -> None:
        pool = async_engine.pool
        assert isinstance(pool, QueuePool)
        checked_out = pool.checkedout()

        async with unit_of_work as uow:
            await uow.tracks.get_list(user_id=user.id)
            assert pool.checkedout() == checked_out + 1

        assert pool.checkedout() == checked_out

    async def test__block_reused__opens_new_session(self, unit_of_work: SQLUnitOfWork) -> None:
        async with unit_of_work:
            first_session = unit_of_work.session

        async with unit_of_work:
            assert isinstance(unit_of_work.session, AsyncSession)
            assert unit_of_work.session is not first_session

        assert unit_of_work.session is None
