import uuid
from dataclasses import replace

from sqlalchemy import ColumnElement
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Playlist]:
        stmt = (
            select(PlaylistModel)
            .where(*self._filters(user_id, type=type, provider=provider))
            # The ID breaks the ties: pages stay stable between two calls
            .order_by(PlaylistModel.created_at.desc(), PlaylistModel.id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return [row.to_entity() for row in result.scalars()]

    async def count(
        self,
        user_id: uuid.UUID,
        type: PlaylistType | None = None,
        provider: MusicProvider | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(PlaylistModel)
            .where(*self._filters(user_id, type=type, provider=provider))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def get(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> Playlist | None:
        playlist = aliased(PlaylistModel, name="playlist")
        track = aliased(TrackModel, name="track")
        plays = TrackPlaySQLRepository.plays_summary(track)
        stmt = (
            select(playlist, track, plays.c.played_count, plays.c.played_at_first, plays.c.played_at_last)
            .outerjoin(PlaylistTrackModel, PlaylistTrackModel.playlist_id == playlist.id)
            .outerjoin(track, track.id == PlaylistTrackModel.track_id)
            .join(plays, true())
            .where(playlist.id == playlist_id, playlist.user_id == user_id)
            .order_by(PlaylistTrackModel.position)
        )

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return None

        playlist_db: PlaylistModel = rows[0].playlist
        tracks = [
            row.track.to_entity(
                played_count=row.played_count,
                played_at_first=row.played_at_first,
                played_at_last=row.played_at_last,
            )
            for row in rows
            if row.track is not None
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
        stmt = delete(PlaylistModel).where(*self._filters(user_id, type=type, provider=provider))

        result = await self.session.execute(stmt.returning(PlaylistModel.id))
        deleted_ids = result.scalars().all()
        return len(deleted_ids)

    @staticmethod
    def _filters(
        user_id: uuid.UUID,
        type: PlaylistType | None,
        provider: MusicProvider | None,
    ) -> list[ColumnElement[bool]]:
        filters = [PlaylistModel.user_id == user_id]

        if type is not None:
            filters.append(PlaylistModel.type == type)
        if provider is not None:
            filters.append(PlaylistModel.provider == provider)

        return filters
