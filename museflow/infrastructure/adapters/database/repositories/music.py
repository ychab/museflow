import dataclasses
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Track
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackOrdering
from museflow.domain.value_objects.music import TrackKnowIdentifiers
from museflow.infrastructure.adapters.database.models import Track as TrackModel


class TrackSQLRepository(TrackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        provider_ids: list[str] | None = None,
        order: TrackOrdering | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        stmt = select(TrackModel).where(TrackModel.user_id == user_id)

        # Filtering
        if provider is not None:
            stmt = stmt.where(TrackModel.provider == provider)

        if provider_ids is not None:
            stmt = stmt.where(TrackModel.provider_id.in_(provider_ids))

        # Ordering
        for order_by, sort_order in order or [(TrackOrderBy.CREATED_AT, SortOrder.ASC)]:
            if order_by == TrackOrderBy.RANDOM:
                stmt = stmt.order_by(func.random())
                break  # RANDOM cannot be combined with further columns

            column = getattr(TrackModel, order_by.value)
            if order_by.nullable:
                stmt = stmt.order_by(
                    column.asc().nulls_last() if sort_order == SortOrder.ASC else column.desc().nulls_last()
                )
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

    async def get_known_identifiers(
        self,
        user_id: uuid.UUID,
        fingerprints: list[str],
    ) -> TrackKnowIdentifiers:
        stmt = select(TrackModel.fingerprint).where(
            TrackModel.user_id == user_id,
            TrackModel.fingerprint.in_(fingerprints),
        )

        result = await self.session.execute(stmt)
        known_fingerprints = frozenset(row.fingerprint for row in result.fetchall())

        return TrackKnowIdentifiers(fingerprints=known_fingerprints)

    async def get_known_provider_ids(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        provider_ids: list[str],
    ) -> frozenset[str]:
        stmt = select(TrackModel.provider_id).where(
            TrackModel.user_id == user_id,
            TrackModel.provider == provider,
            TrackModel.provider_id.in_(provider_ids),
        )
        result = await self.session.execute(stmt)

        return frozenset(row.provider_id for row in result.fetchall())

    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[list[uuid.UUID], int]:
        track_ids: list[uuid.UUID] = []
        created_count: int = 0

        index_elements: list[str] = ["user_id", "provider_id"]
        index_excluded: list[str] = ["id"] + index_elements

        tracks_dicts: list[dict[str, Any]] = [dataclasses.asdict(track) for track in tracks]

        total: int = len(tracks_dicts)
        for offset in range(0, total, batch_size):
            tracks_chunk = tracks_dicts[offset : offset + batch_size]

            stmt = pg_insert(TrackModel).values(tracks_chunk)
            excluded = stmt.excluded

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_={
                    key: (
                        func.greatest(getattr(TrackModel, key), excluded[key]) if key == "played_at" else excluded[key]
                    )
                    for key in tracks_chunk[0]
                    if key not in index_excluded
                },
            ).returning(
                TrackModel.id,
                text("(xmax = 0) AS was_created"),
            )

            results = await self.session.execute(upsert_stmt)
            rows = results.all()

            track_ids.extend([row[0] for row in rows])
            created_count += sum(row[1] for row in rows)

        await self.session.commit()

        return track_ids, created_count

    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        stmt = delete(TrackModel).where(TrackModel.user_id == user_id, TrackModel.provider == provider)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore
