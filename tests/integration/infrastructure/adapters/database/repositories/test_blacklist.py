import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.domain.entities.user import User
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedArtist as BlacklistedArtistModel
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedTrack as BlacklistedTrackModel

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestBlacklistSQLRepository:
    async def test__add_artist__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        entity = await blacklist_repository.add_artist(user_id=user.id, artist_name="Taylor Swift")

        assert entity.user_id == user.id
        assert entity.artist_name == "Taylor Swift"
        assert entity.fingerprint == normalize_text("Taylor Swift")

        count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedArtistModel).where(BlacklistedArtistModel.id == entity.id)
            )
        ).scalar()
        assert count == 1

    async def test__add_artist__idempotent(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        entity_1 = await blacklist_repository.add_artist(user_id=user.id, artist_name="Taylor Swift")
        entity_2 = await blacklist_repository.add_artist(user_id=user.id, artist_name="Taylor Swift")

        assert entity_1.id == entity_2.id

    async def test__add_track__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        entity = await blacklist_repository.add_track(user_id=user.id, name="Shake It Off", artist_name="Taylor Swift")

        assert entity.user_id == user.id
        assert entity.name == "Shake It Off"
        assert entity.artist_name == "Taylor Swift"
        assert entity.fingerprint == generate_fingerprint("Shake It Off", ["Taylor Swift"])

        count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedTrackModel).where(BlacklistedTrackModel.id == entity.id)
            )
        ).scalar()
        assert count == 1

    async def test__add_track__idempotent(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        entity_1 = await blacklist_repository.add_track(
            user_id=user.id, name="Shake It Off", artist_name="Taylor Swift"
        )
        entity_2 = await blacklist_repository.add_track(
            user_id=user.id, name="Shake It Off", artist_name="Taylor Swift"
        )

        assert entity_1.id == entity_2.id

    async def test__remove__artist(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)

        await blacklist_repository.remove(user_id=user.id, item_ids=[artist_db.id])

        count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(BlacklistedArtistModel)
                .where(BlacklistedArtistModel.id == artist_db.id)
            )
        ).scalar()
        assert count == 0

    async def test__remove__track(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        await blacklist_repository.remove(user_id=user.id, item_ids=[track_db.id])

        count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedTrackModel).where(BlacklistedTrackModel.id == track_db.id)
            )
        ).scalar()
        assert count == 0

    async def test__remove__multiple(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        await blacklist_repository.remove(user_id=user.id, item_ids=[artist_db.id, track_db.id])

        artist_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(BlacklistedArtistModel)
                .where(BlacklistedArtistModel.user_id == user.id)
            )
        ).scalar()
        track_count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedTrackModel).where(BlacklistedTrackModel.user_id == user.id)
            )
        ).scalar()
        assert artist_count == 0
        assert track_count == 0

    async def test__remove__not_found(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        missing_id = uuid.uuid4()
        removed = await blacklist_repository.remove(user_id=user.id, item_ids=[missing_id])
        assert removed == set()

    async def test__remove__partial_not_found(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        missing_id = uuid.uuid4()

        removed = await blacklist_repository.remove(user_id=user.id, item_ids=[artist_db.id, missing_id])

        assert removed == {artist_db.id}
        count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(BlacklistedArtistModel)
                .where(BlacklistedArtistModel.id == artist_db.id)
            )
        ).scalar()
        assert count == 0

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedTrackModelFactory.create_async(user_id=user.id)

        count = await blacklist_repository.purge(user_id=user.id)

        assert count == 3

        artist_count = (
            await async_session_db.execute(
                select(func.count())
                .select_from(BlacklistedArtistModel)
                .where(BlacklistedArtistModel.user_id == user.id)
            )
        ).scalar()
        track_count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedTrackModel).where(BlacklistedTrackModel.user_id == user.id)
            )
        ).scalar()
        assert artist_count == 0
        assert track_count == 0

    async def test__get_all__empty(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        result = await blacklist_repository.get_all(user_id=user.id)

        assert result.is_empty is True
        assert result.artists == []
        assert result.tracks == []

    async def test__get_all__with_entries(
        self,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)
        await BlacklistedArtistModelFactory.create_async()  # another user

        result = await blacklist_repository.get_all(user_id=user.id)

        assert len(result.artists) == 1
        assert result.artists[0].id == artist_db.id
        assert len(result.tracks) == 1
        assert result.tracks[0].id == track_db.id
