import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.track import Track as TrackModel
from museflow.infrastructure.adapters.database.repositories.playlist import PlaylistSQLRepository
from museflow.infrastructure.adapters.database.repositories.track import TrackSQLRepository
from museflow.infrastructure.adapters.database.session import async_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory


class TestSQLUnitOfWork:
    """Real commits (`async_session_trans`): the default session turns commits into flushes and would hide them."""

    @pytest.fixture
    def unit_of_work(self, async_session_trans: AsyncSession) -> SQLUnitOfWork:
        return SQLUnitOfWork(async_session_trans)

    @pytest.fixture
    def track_repository(self, async_session_trans: AsyncSession) -> TrackRepository:
        return TrackSQLRepository(async_session_trans)

    @pytest.fixture
    def playlist_repository(self, async_session_trans: AsyncSession) -> PlaylistRepository:
        return PlaylistSQLRepository(async_session_trans)

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

    async def test__block_succeeds__writes_committed_together(
        self,
        unit_of_work: SQLUnitOfWork,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        user: User,
        tracks: list[Track],
    ) -> None:
        async with unit_of_work.atomic():
            await track_repository.bulk_upsert(tracks, batch_size=100)
            assert await self.count_rows(user.id) == (0, 0)

            tracks_db = await track_repository.get_list(user_id=user.id)
            await playlist_repository.save(PlaylistFactory.build(user_id=user.id, profile_id=None, tracks=tracks_db))
            assert await self.count_rows(user.id) == (0, 0)

        assert await self.count_rows(user.id) == (2, 1)

    async def test__block_fails__writes_rolled_back(
        self,
        unit_of_work: SQLUnitOfWork,
        track_repository: TrackRepository,
        playlist_repository: PlaylistRepository,
        user: User,
        tracks: list[Track],
    ) -> None:
        with pytest.raises(IntegrityError):
            async with unit_of_work.atomic():
                await track_repository.bulk_upsert(tracks, batch_size=100)
                tracks_db = await track_repository.get_list(user_id=user.id)
                # Unknown owner: the foreign key fails, as a database failure would.
                await playlist_repository.save(
                    PlaylistFactory.build(user_id=uuid.uuid4(), profile_id=None, tracks=tracks_db)
                )

        assert await self.count_rows(user.id) == (0, 0)

        # The session commits again on its own after the block.
        await track_repository.bulk_upsert(tracks, batch_size=100)
        assert await self.count_rows(user.id) == (2, 0)
