import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopItem
from spotifagent.domain.entities.music import TopTrack
from spotifagent.domain.ports.repositories.music import TopArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TopTrackRepositoryPort
from spotifagent.infrastructure.adapters.database.models import TopArtist as TopArtistModel
from spotifagent.infrastructure.adapters.database.models import TopMusicMixin
from spotifagent.infrastructure.adapters.database.models import TopTrack as TopTrackModel


class TopArtistRepository(TopArtistRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert(self, top_artists: list[TopArtist], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_top_item_upsert(
            session=self.session,
            sql_model=TopArtistModel,
            top_items=top_artists,
            batch_size=batch_size,
        )

    async def purge(self, user_id: uuid.UUID) -> int:
        stmt = delete(TopArtistModel).where(TopArtistModel.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore


class TopTrackRepository(TopTrackRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert(self, top_tracks: list[TopTrack], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_top_item_upsert(
            session=self.session,
            sql_model=TopTrackModel,
            top_items=top_tracks,
            batch_size=batch_size,
        )

    async def purge(self, user_id: uuid.UUID) -> int:
        stmt = delete(TopTrackModel).where(TopTrackModel.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore


async def bulk_top_item_upsert[TopItemModel: TopMusicMixin, TopItemType: TopItem](
    session: AsyncSession,
    sql_model: type[TopItemModel],
    top_items: list[TopItemType],
    batch_size: int,
) -> tuple[list[uuid.UUID], int]:
    top_item_ids: list[uuid.UUID] = []
    created_count: int = 0

    index_elements: list[str] = ["user_id", "provider_id"]
    index_excluded: list[str] = ["id"] + index_elements

    top_items_dicts: list[dict[str, Any]] = [top_item.model_dump(mode="json") for top_item in top_items]

    total: int = len(top_items_dicts)
    for offset in range(0, total, batch_size):
        top_items_chunk = top_items_dicts[offset : offset + batch_size]

        stmt = pg_insert(sql_model).values(top_items_chunk)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={key: getattr(stmt.excluded, key) for key in top_items_chunk[0] if key not in index_excluded},
        ).returning(
            sql_model.id,
            text("(xmax = 0) AS was_created"),
        )

        results = await session.execute(upsert_stmt)
        rows = results.all()

        top_item_ids.extend([row[0] for row in rows])
        created_count += sum(row[1] for row in rows)

    await session.commit()

    return top_item_ids, created_count
