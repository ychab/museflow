import uuid
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.discovery import DiscoveryPlaylist
from museflow.infrastructure.adapters.database.models.discovery import DiscoveryPlaylist as DiscoveryPlaylistDB
from museflow.infrastructure.adapters.database.models.discovery import (
    DiscoveryPlaylistTrack as DiscoveryPlaylistTrackDB,
)
from museflow.infrastructure.adapters.database.models.music import Track as TrackDB


class DiscoveryPlaylistSQLRepository(DiscoveryPlaylistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, playlist: DiscoveryPlaylist) -> DiscoveryPlaylist:
        playlist_db = DiscoveryPlaylistDB.from_entity(playlist)
        self.session.add(playlist_db)

        for i, track in enumerate(playlist.tracks):
            self.session.add(DiscoveryPlaylistTrackDB(playlist_id=playlist.id, track_id=track.id, position=i))

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
            select(DiscoveryPlaylistDB, TrackDB)
            .join(DiscoveryPlaylistTrackDB, DiscoveryPlaylistTrackDB.playlist_id == DiscoveryPlaylistDB.id)
            .join(TrackDB, TrackDB.id == DiscoveryPlaylistTrackDB.track_id)
            .where(DiscoveryPlaylistDB.id == playlist_id, DiscoveryPlaylistDB.user_id == user_id)
            .order_by(DiscoveryPlaylistTrackDB.position)
        )

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return None

        playlist_db, _ = rows[0]
        tracks = [track_db.to_entity() for _, track_db in rows]
        return replace(playlist_db.to_entity(), tracks=tracks)
