import uuid
from dataclasses import replace

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import true
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.playlist import Playlist
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.adapters.database.models.playlist import PlaylistModel
from museflow.infrastructure.adapters.database.models.playlist import PlaylistTrackModel
from museflow.infrastructure.adapters.database.models.track import TrackModel
from museflow.infrastructure.adapters.database.repositories.track_play import TrackPlaySQLRepository


class PlaylistSQLRepository(PlaylistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, playlist: Playlist) -> Playlist:
        playlist_db = PlaylistModel.from_entity(playlist)
        self.session.add(playlist_db)

        for i, track in enumerate(playlist.tracks):
            self.session.add(PlaylistTrackModel(playlist_id=playlist.id, track_id=track.id, position=i))

        await self.session.flush()
        await self.session.refresh(playlist_db)

        return replace(playlist_db.to_entity(), tracks=playlist.tracks)

    async def get_list(
        self,
        user_id: uuid.UUID,
        type: PlaylistType | None = None,
        provider: MusicProvider | None = None,
    ) -> list[Playlist]:
        stmt = select(PlaylistModel).where(PlaylistModel.user_id == user_id).order_by(PlaylistModel.created_at.desc())
        if type is not None:
            stmt = stmt.where(PlaylistModel.type == type)
        if provider is not None:
            stmt = stmt.where(PlaylistModel.provider == provider)
        result = await self.session.execute(stmt)
        return [row.to_entity() for row in result.scalars()]

    async def get(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> Playlist | None:
        plays = TrackPlaySQLRepository.plays_summary()
        stmt = (
            select(PlaylistModel, TrackModel, plays.c.played_count, plays.c.played_at_first, plays.c.played_at_last)
            .outerjoin(PlaylistTrackModel, PlaylistTrackModel.playlist_id == PlaylistModel.id)
            .outerjoin(TrackModel, TrackModel.id == PlaylistTrackModel.track_id)
            .join(plays, true())
            .where(PlaylistModel.id == playlist_id, PlaylistModel.user_id == user_id)
            .order_by(PlaylistTrackModel.position)
        )

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return None

        playlist_db: PlaylistModel = rows[0]._mapping[PlaylistModel]
        tracks = [
            track_db.to_entity(played_count=played_count, played_at_first=first, played_at_last=last)
            for _, track_db, played_count, first, last in rows
            if track_db is not None
        ]
        return replace(playlist_db.to_entity(), tracks=tracks)

    async def get_track_ids(self, user_id: uuid.UUID, type: PlaylistType) -> frozenset[uuid.UUID]:
        stmt = (
            select(PlaylistTrackModel.track_id)
            .join(PlaylistModel, PlaylistModel.id == PlaylistTrackModel.playlist_id)
            .where(PlaylistModel.user_id == user_id, PlaylistModel.type == type)
            .distinct()
        )
        result = await self.session.execute(stmt)
        return frozenset(result.scalars().all())

    async def delete(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> bool:
        stmt = (
            delete(PlaylistModel)
            .where(PlaylistModel.id == playlist_id, PlaylistModel.user_id == user_id)
            .returning(PlaylistModel.id)
        )
        result = await self.session.execute(stmt)
        deleted = result.scalar_one_or_none() is not None
        return deleted

    async def purge(
        self,
        user_id: uuid.UUID,
        type: PlaylistType | None = None,
        provider: MusicProvider | None = None,
    ) -> int:
        stmt = delete(PlaylistModel).where(PlaylistModel.user_id == user_id)
        if type is not None:
            stmt = stmt.where(PlaylistModel.type == type)
        if provider is not None:
            stmt = stmt.where(PlaylistModel.provider == provider)

        result = await self.session.execute(stmt.returning(PlaylistModel.id))
        deleted_ids = result.scalars().all()
        return len(deleted_ids)
