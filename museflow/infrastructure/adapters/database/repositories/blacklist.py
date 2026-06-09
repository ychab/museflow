import uuid

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedArtist as BlacklistedArtistModel
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedTrack as BlacklistedTrackModel


class BlacklistSQLRepository(BlacklistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_artist(self, user_id: uuid.UUID, artist_name: str) -> BlacklistedArtist:
        insert_stmt = pg_insert(BlacklistedArtistModel).values(
            id=uuid.uuid4(),
            user_id=user_id,
            artist_name=artist_name,
            fingerprint=normalize_text(artist_name),
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["user_id", "fingerprint"],
            set_={"artist_name": insert_stmt.excluded.artist_name},
        ).returning(BlacklistedArtistModel)

        row = (await self.session.execute(upsert_stmt)).scalar_one()
        await self.session.commit()

        return row.to_entity()

    async def add_track(self, user_id: uuid.UUID, name: str, artist_name: str) -> BlacklistedTrack:
        insert_stmt = pg_insert(BlacklistedTrackModel).values(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            artist_name=artist_name,
            fingerprint=generate_fingerprint(name, [artist_name]),
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["user_id", "fingerprint"],
            set_={"name": insert_stmt.excluded.name, "artist_name": insert_stmt.excluded.artist_name},
        ).returning(BlacklistedTrackModel)

        row = (await self.session.execute(upsert_stmt)).scalar_one()
        await self.session.commit()

        return row.to_entity()

    async def remove(self, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        artist_del = await self.session.execute(
            delete(BlacklistedArtistModel)
            .where(BlacklistedArtistModel.id.in_(item_ids), BlacklistedArtistModel.user_id == user_id)
            .returning(BlacklistedArtistModel.id)
        )
        track_del = await self.session.execute(
            delete(BlacklistedTrackModel)
            .where(BlacklistedTrackModel.id.in_(item_ids), BlacklistedTrackModel.user_id == user_id)
            .returning(BlacklistedTrackModel.id)
        )
        removed: set[uuid.UUID] = set(artist_del.scalars()) | set(track_del.scalars())
        await self.session.commit()
        return removed

    async def purge(self, user_id: uuid.UUID) -> int:
        deleted_artists = await self.session.execute(
            delete(BlacklistedArtistModel).where(BlacklistedArtistModel.user_id == user_id)
        )
        deleted_tracks = await self.session.execute(
            delete(BlacklistedTrackModel).where(BlacklistedTrackModel.user_id == user_id)
        )

        total = int(deleted_artists.rowcount) + int(deleted_tracks.rowcount)  # type: ignore[union-attr, attr-defined]
        await self.session.commit()

        return total

    async def get_all(self, user_id: uuid.UUID) -> UserBlacklist:
        artists_result = await self.session.execute(
            select(BlacklistedArtistModel).where(BlacklistedArtistModel.user_id == user_id)
        )
        tracks_result = await self.session.execute(
            select(BlacklistedTrackModel).where(BlacklistedTrackModel.user_id == user_id)
        )
        return UserBlacklist(
            artists=[row.to_entity() for row in artists_result.scalars().all()],
            tracks=[row.to_entity() for row in tracks_result.scalars().all()],
        )
