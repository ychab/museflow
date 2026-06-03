import uuid
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.discovery import DiscoveryPlaylist
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.infrastructure.adapters.database.models.discovery import DiscoveryPlaylist as DiscoveryPlaylistDB
from museflow.infrastructure.adapters.database.models.discovery import (
    DiscoveryPlaylistTrack as DiscoveryPlaylistTrackDB,
)


class DiscoveryPlaylistSQLRepository(DiscoveryPlaylistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, playlist: DiscoveryPlaylist) -> DiscoveryPlaylist:
        playlist_db = DiscoveryPlaylistDB.from_entity(playlist)
        self.session.add(playlist_db)

        for track in playlist.tracks:
            self.session.add(DiscoveryPlaylistTrackDB.from_entity(track))

        await self.session.commit()
        await self.session.refresh(playlist_db)
        return replace(playlist_db.to_entity(), tracks=playlist.tracks)

    async def list(self, user_id: uuid.UUID) -> list[DiscoveryPlaylist]:
        stmt = (
            select(DiscoveryPlaylistDB)
            .where(DiscoveryPlaylistDB.user_id == user_id)
            .order_by(DiscoveryPlaylistDB.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [row.to_entity() for row in result.scalars()]

    async def get(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> DiscoveryPlaylist | None:
        stmt = (
            select(DiscoveryPlaylistDB, DiscoveryPlaylistTrackDB)
            .join(DiscoveryPlaylistTrackDB, DiscoveryPlaylistTrackDB.playlist_id == DiscoveryPlaylistDB.id)
            .where(DiscoveryPlaylistDB.id == playlist_id, DiscoveryPlaylistDB.user_id == user_id)
            .order_by(DiscoveryPlaylistTrackDB.position)
        )

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return None

        playlist_db, _ = rows[0]
        tracks = [track_db.to_entity() for _, track_db in rows]
        return replace(playlist_db.to_entity(), tracks=tracks)

    async def rate_track(self, user_id: uuid.UUID, track_id: uuid.UUID, score: int) -> None:
        stmt = (
            update(DiscoveryPlaylistTrackDB)
            .where(
                DiscoveryPlaylistTrackDB.id == track_id,
                DiscoveryPlaylistTrackDB.playlist_id.in_(
                    select(DiscoveryPlaylistDB.id).where(DiscoveryPlaylistDB.user_id == user_id)
                ),
            )
            .values(score=score)
            .returning(DiscoveryPlaylistTrackDB.id)
        )

        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise DiscoveryPlaylistNotFoundError()

        await self.session.commit()
