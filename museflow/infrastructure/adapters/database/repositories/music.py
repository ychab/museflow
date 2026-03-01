import dataclasses
import uuid
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import BaseMediaItem
from museflow.domain.entities.music import Track
from museflow.domain.ports.repositories.music import ArtistRepository
from museflow.domain.ports.repositories.music import TrackRepository
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.infrastructure.adapters.database.models import Artist as ArtistModel
from museflow.infrastructure.adapters.database.models import MusicItemMixin
from museflow.infrastructure.adapters.database.models import Track as TrackModel


class ArtistSQLRepository(ArtistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Artist]:
        stmt = select(ArtistModel).where(ArtistModel.user_id == user_id).order_by("created_at")

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        results = await self.session.execute(stmt)
        return [artist_db.to_entity() for artist_db in results.scalars().all()]

    async def bulk_upsert(self, artists: list[Artist], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_item_upsert(
            session=self.session,
            sql_model=ArtistModel,
            items=artists,
            batch_size=batch_size,
        )

    async def purge(self, user_id: uuid.UUID) -> int:
        stmt = delete(ArtistModel).where(ArtistModel.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore


class TrackSQLRepository(TrackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        is_top: bool | None = None,
        is_saved: bool | None = None,
        order_by: TrackOrderBy = TrackOrderBy.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        stmt = select(TrackModel).where(TrackModel.user_id == user_id)

        # Filtering
        if is_top is not None:
            stmt = stmt.where(TrackModel.is_top == is_top)
        if is_saved is not None:
            stmt = stmt.where(TrackModel.is_saved == is_saved)

        # Ordering
        column = getattr(TrackModel, order_by.value, TrackModel.created_at)
        if order_by == TrackOrderBy.RANDOM:
            stmt = stmt.order_by(func.random())
        elif sort_order == SortOrder.DESC:
            stmt = stmt.order_by(column.desc())
        else:
            stmt = stmt.order_by(column.asc())

        # Pagination
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        results = await self.session.execute(stmt)
        return [tracks_db.to_entity() for tracks_db in results.scalars().all()]

    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_item_upsert(
            session=self.session,
            sql_model=TrackModel,
            items=tracks,
            batch_size=batch_size,
        )

    async def purge(
        self,
        user_id: uuid.UUID,
        is_top: bool = False,
        is_saved: bool = False,
        is_playlist: bool = False,
    ) -> int:
        conditions = [TrackModel.user_id == user_id]

        or_filters: list[ColumnElement[bool]] = []
        if is_top:
            or_filters.append(TrackModel.is_top.is_(True))
        if is_saved:
            or_filters.append(TrackModel.is_saved.is_(True))
        if is_playlist:
            or_filters.append(and_(TrackModel.is_top.is_(False), TrackModel.is_saved.is_(False)))

        if or_filters:
            conditions.append(or_(*or_filters))

        stmt = delete(TrackModel).where(*conditions)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore


async def bulk_item_upsert[ItemModel: MusicItemMixin, ItemEntity: BaseMediaItem](
    session: AsyncSession,
    sql_model: type[ItemModel],
    items: list[ItemEntity],
    batch_size: int,
) -> tuple[list[uuid.UUID], int]:
    item_ids: list[uuid.UUID] = []
    created_count: int = 0

    index_elements: list[str] = ["user_id", "provider_id"]
    index_excluded: list[str] = ["id"] + index_elements

    items_dicts: list[dict[str, Any]] = [dataclasses.asdict(item) for item in items]

    total: int = len(items_dicts)
    for offset in range(0, total, batch_size):
        items_chunk = items_dicts[offset : offset + batch_size]

        stmt = pg_insert(sql_model).values(items_chunk)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={key: getattr(stmt.excluded, key) for key in items_chunk[0] if key not in index_excluded},
        ).returning(
            sql_model.id,
            text("(xmax = 0) AS was_created"),
        )

        results = await session.execute(upsert_stmt)
        rows = results.all()

        item_ids.extend([row[0] for row in rows])
        created_count += sum(row[1] for row in rows)

    await session.commit()

    return item_ids, created_count
