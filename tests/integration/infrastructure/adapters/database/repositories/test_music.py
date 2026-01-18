from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.music import TopArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TopTrackRepositoryPort
from spotifagent.infrastructure.adapters.database.models import TopArtist as TopArtistModel
from spotifagent.infrastructure.adapters.database.models import TopTrack as TopTrackModel

from tests.integration.factories.music import TopArtistModelFactory
from tests.integration.factories.music import TopTrackModelFactory
from tests.unit.factories.music import TopArtistFactory
from tests.unit.factories.music import TopTrackFactory


class TestTopArtistRepository:
    @pytest.fixture
    async def top_artists(self, user: User) -> list[TopArtist]:
        top_artists_db = await TopArtistModelFactory.create_batch_async(size=10, user_id=user.id)
        return [TopArtist.model_validate(top_artist_db) for top_artist_db in top_artists_db]

    @pytest.fixture
    def top_artists_create(self, user: User) -> list[TopArtist]:
        return TopArtistFactory.batch(size=10, user_id=user.id)

    @pytest.fixture
    def top_artists_update(self, top_artists: list[TopArtist]) -> list[TopArtist]:
        return [TopArtist.model_validate({**top_artist.model_dump(), "genres": ["foo"]}) for top_artist in top_artists]

    @pytest.fixture
    def top_artists_mix(self, user: User, top_artists: list[TopArtist]) -> list[TopArtist]:
        return [
            *TopArtistFactory.batch(size=5, user_id=user.id),  # 5 created
            *[
                TopArtist.model_validate({**top_artist.model_dump(), "genres": ["foo"]})
                for top_artist in top_artists[:5]
            ],  # 5 updated
        ]

    @pytest.fixture
    async def top_artists_delete(self, user: User) -> list[TopArtist]:
        top_artists_user = await TopArtistModelFactory.create_batch_async(size=3, user_id=user.id)
        top_artists_others = await TopArtistModelFactory.create_batch_async(size=2)

        return [TopArtist.model_validate(top_artist_db) for top_artist_db in top_artists_user + top_artists_others]

    async def test__bulk_upsert__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_create: list[TopArtist],
        top_artist_repository: TopArtistRepositoryPort,
    ) -> None:
        top_artist_ids, create_count = await top_artist_repository.bulk_upsert(
            top_artists_create,
            batch_size=int(len(top_artists_create) / 5),
        )

        # Check that we have the expected number of items.
        assert len(top_artist_ids) == len(top_artists_create) == create_count == 10

        # Check that objects has been really created in DB.
        stmt = select(TopArtistModel).where(TopArtistModel.id.in_(top_artist_ids))
        results = await async_session_db.execute(stmt)
        top_artists_db = results.scalars().all()
        assert len(top_artists_db) == len(top_artist_ids)

        # Check that top items have been created only for that user.
        assert set([ta.user_id for ta in top_artists_db]) == {user.id}
        # Check that at least one field was inserted as expected.
        assert sorted([ta.provider_id for ta in top_artists_db]) == sorted(
            [str(ta.provider_id) for ta in top_artists_create]
        )

    async def test__bulk_upsert__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists: list[TopArtist],
        top_artists_update: list[TopArtist],
        top_artist_repository: TopArtistRepositoryPort,
    ) -> None:
        top_artist_ids, create_count = await top_artist_repository.bulk_upsert(
            top_artists_update,
            batch_size=int(len(top_artists_update) / 5),
        )

        # Check that we have the expected number of items.
        assert len(top_artist_ids) == len(top_artists_update) == len(top_artists) == 10
        assert create_count == 0

        # Check that objects has been really updated in DB.
        stmt = select(TopArtistModel).where(TopArtistModel.id.in_(top_artist_ids))
        results = await async_session_db.execute(stmt)
        top_artists_db = results.scalars().all()
        assert len(top_artists_db) == len(top_artists_update)

        # Check that top items have been created only for that user.
        assert set([ta.user_id for ta in top_artists_db]) == {user.id}
        # Check that at least one field was updated as expected.
        assert set([top_artist_db.genres[0] for top_artist_db in top_artists_db]) == {"foo"}

    async def test__bulk_upsert__both(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_mix: list[TopArtist],
        top_artist_repository: TopArtistRepositoryPort,
    ) -> None:
        top_artist_ids, create_count = await top_artist_repository.bulk_upsert(top_artists_mix, 300)

        # Check that we have the expected number of items.
        assert len(top_artist_ids) == len(top_artists_mix) == 10
        assert create_count == 5

        # Check that objects has been really updated in DB.
        stmt = (
            select(TopArtistModel)
            .where(TopArtistModel.id.in_(top_artist_ids))
            .order_by(TopArtistModel.created_at.asc())
        )
        results = await async_session_db.execute(stmt)
        top_artists_db = results.scalars().all()
        assert len(top_artists_db) == len(top_artists_mix)

        # Check that top items have been upserted only for that user.
        assert set([ta.user_id for ta in top_artists_db]) == {user.id}

        # Check created as expected.
        assert sorted([ta.provider_id for ta in top_artists_db[:5]]) == sorted(
            [str(ta.provider_id) for ta in top_artists_mix[:5]]
        )
        # Check updated as expected.
        assert set([ta.genres[0] for ta in top_artists_db[5:]]) == {"foo"}

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_artists_delete: list[TopArtist],
        top_artist_repository: TopArtistRepositoryPort,
    ) -> None:
        count = await top_artist_repository.purge(user.id)
        assert count == 3

        # Check if all top artists have been deleted for that user.
        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id == user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 0

        # Be sure to keep other users tops!
        stmt = select(func.count()).select_from(TopArtistModel).where(TopArtistModel.user_id != user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 2


class TestTopTrackRepository:
    @pytest.fixture
    async def top_tracks(self, user: User) -> list[TopTrack]:
        top_tracks_db = await TopTrackModelFactory.create_batch_async(size=10, user_id=user.id)
        return [TopTrack.model_validate(top_track_db) for top_track_db in top_tracks_db]

    @pytest.fixture
    def top_tracks_create(self, user: User) -> list[TopTrack]:
        return TopTrackFactory.batch(size=10, user_id=user.id)

    @pytest.fixture
    def top_tracks_update(self, top_tracks: list[TopTrack]) -> list[TopTrack]:
        return [
            TopTrack.model_validate({**top_track.model_dump(), "artists": [{"name": "SCH", "provider_id": "foo"}]})
            for top_track in top_tracks
        ]

    @pytest.fixture
    def top_tracks_mix(self, user: User, top_tracks: list[TopTrack]) -> list[TopTrack]:
        return [
            *TopTrackFactory.batch(size=5, user_id=user.id),  # 5 created
            *[
                TopTrack.model_validate({**top_track.model_dump(), "artists": [{"name": "SCH", "provider_id": "foo"}]})
                for top_track in top_tracks[:5]
            ],  # 5 updated
        ]

    @pytest.fixture
    async def top_tracks_delete(self, user: User) -> list[TopTrack]:
        top_tracks_user = await TopTrackModelFactory.create_batch_async(size=3, user_id=user.id)
        top_tracks_others = await TopTrackModelFactory.create_batch_async(size=2)

        return [TopTrack.model_validate(top_track_db) for top_track_db in top_tracks_user + top_tracks_others]

    async def test__bulk_upsert__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks_create: list[TopTrack],
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        top_track_ids, create_count = await top_track_repository.bulk_upsert(
            top_tracks_create,
            batch_size=int(len(top_tracks_create) / 5),
        )

        # Check that we have the expected number of items.
        assert len(top_track_ids) == len(top_tracks_create) == create_count == 10

        # Check that objects has been really created in DB.
        stmt = select(TopTrackModel).where(TopTrackModel.id.in_(top_track_ids))
        results = await async_session_db.execute(stmt)
        top_tracks_db = results.scalars().all()

        assert len(top_tracks_db) == len(top_track_ids)
        assert set([ta.user_id for ta in top_tracks_db]) == {user.id}
        assert sorted([ta.provider_id for ta in top_tracks_db]) == sorted(
            [str(ta.provider_id) for ta in top_tracks_create]
        )

    async def test__bulk_upsert__update(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks: list[TopTrack],
        top_tracks_update: list[TopTrack],
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        top_track_ids, create_count = await top_track_repository.bulk_upsert(
            top_tracks_update,
            batch_size=int(len(top_tracks_update) / 5),
        )

        # Check that we have the expected number of items.
        assert len(top_track_ids) == len(top_tracks_update) == len(top_tracks) == 10
        assert create_count == 0

        # Check that objects has been really updated in DB.
        stmt = select(TopTrackModel).where(TopTrackModel.id.in_(top_track_ids))
        results = await async_session_db.execute(stmt)
        top_tracks_db = results.scalars().all()

        assert len(top_tracks_db) == len(top_tracks_update)
        assert set([ta.user_id for ta in top_tracks_db]) == {user.id}

        artists = [top_track_db.artists[0] for top_track_db in top_tracks_db]
        expected_artists = [{"name": "SCH", "provider_id": "foo"} for _ in range(len(top_tracks_db))]
        assert artists == expected_artists

    async def test__bulk_upsert__both(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks_mix: list[TopTrack],
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        top_track_ids, create_count = await top_track_repository.bulk_upsert(top_tracks_mix, 300)

        # Check that we have the expected number of items.
        assert len(top_track_ids) == len(top_tracks_mix) == 10
        assert create_count == 5

        # Check that objects has been really updated in DB.
        stmt = (
            select(TopTrackModel).where(TopTrackModel.id.in_(top_track_ids)).order_by(TopTrackModel.created_at.asc())
        )
        results = await async_session_db.execute(stmt)
        top_tracks_db = results.scalars().all()
        assert len(top_tracks_db) == len(top_tracks_mix)
        assert set([ta.user_id for ta in top_tracks_db]) == {user.id}

        # Check created as expected.
        assert sorted([ta.provider_id for ta in top_tracks_db[:5]]) == sorted(
            [str(ta.provider_id) for ta in top_tracks_mix[:5]]
        )
        # Check updated as expected.
        artists = [top_track_db.artists[0] for top_track_db in top_tracks_db[5:]]
        expected_artists = [{"name": "SCH", "provider_id": "foo"} for _ in range(len(top_tracks_db[5:]))]
        assert artists == expected_artists

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        top_tracks_delete: list[TopTrack],
        top_track_repository: TopTrackRepositoryPort,
    ) -> None:
        count = await top_track_repository.purge(user.id)
        assert count == 3

        # Check if all top artists have been deleted for that user.
        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id == user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 0

        # Be sure to keep other users tops!
        stmt = select(func.count()).select_from(TopTrackModel).where(TopTrackModel.user_id != user.id)
        results = await async_session_db.execute(stmt)
        assert results.scalar() == 2
