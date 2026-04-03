import dataclasses
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import BaseMediaItem
from museflow.domain.entities.music import Track
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackSource
from museflow.domain.value_objects.music import TrackKnowIdentifiers
from museflow.infrastructure.adapters.database.models import Artist as ArtistModel
from museflow.infrastructure.adapters.database.models import MusicItemMixin
from museflow.infrastructure.adapters.database.models import Track as TrackModel


class ArtistSQLRepository(ArtistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Artist]:
        stmt = select(ArtistModel).where(ArtistModel.user_id == user_id)

        if provider is not None:
            stmt = stmt.where(ArtistModel.provider == provider)

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        stmt = stmt.order_by("created_at")

        results = await self.session.execute(stmt)
        return [artist_db.to_entity() for artist_db in results.scalars().all()]

    async def bulk_upsert(self, artists: list[Artist], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_item_upsert(
            session=self.session,
            sql_model=ArtistModel,
            items=artists,
            batch_size=batch_size,
        )

    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        stmt = delete(ArtistModel).where(ArtistModel.user_id == user_id, ArtistModel.provider == provider)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore


class TrackSQLRepository(TrackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        sources: TrackSource | None = None,
        genres: list[str] | None = None,
        order_by: TrackOrderBy = TrackOrderBy.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        stmt = select(TrackModel).where(TrackModel.user_id == user_id)

        # Filtering
        if provider is not None:
            stmt = stmt.where(TrackModel.provider == provider)

        if sources is not None:
            stmt = stmt.where(TrackModel.sources.op("&")(int(sources)) != 0)

        if genres:
            # Does a Track's artist exist for this user with matching genres?
            artist_conditions = [
                ArtistModel.user_id == user_id,
                ArtistModel.genres.overlap(genres),
                TrackModel.artists.contains(
                    func.jsonb_build_array(func.jsonb_build_object("provider_id", ArtistModel.provider_id))
                ),
            ]
            if provider is not None:
                artist_conditions.append(ArtistModel.provider == provider)

            artist_subquery = select(1).where(*artist_conditions).correlate(TrackModel)

            stmt = stmt.where(
                or_(
                    TrackModel.genres.overlap(genres),  # Track genres
                    artist_subquery.exists(),  # Fallback: Artists genres
                )
            )

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

    async def get_known_identifiers(
        self,
        user_id: uuid.UUID,
        isrcs: list[str],
        fingerprints: list[str],
    ) -> TrackKnowIdentifiers:
        stmt = select(TrackModel.isrc, TrackModel.fingerprint).where(TrackModel.user_id == user_id)

        conditions = []
        if isrcs:
            conditions.append(TrackModel.isrc.in_(isrcs))
        if fingerprints:
            conditions.append(TrackModel.fingerprint.in_(fingerprints))

        if conditions:
            stmt = stmt.where(or_(*conditions))

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        known_isrcs = frozenset(row.isrc for row in rows if row.isrc)
        known_fingerprints = frozenset(row.fingerprint for row in rows if row.fingerprint)

        return TrackKnowIdentifiers(isrcs=known_isrcs, fingerprints=known_fingerprints)

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

    async def get_distinct_genres(self, user_id: uuid.UUID, provider: MusicProvider | None = None) -> list[str]:
        # Subquery to get genres from artists
        stmt_artist = select(func.unnest(ArtistModel.genres).label("genre")).where(ArtistModel.user_id == user_id)
        if provider is not None:
            stmt_artist = stmt_artist.where(ArtistModel.provider == provider)

        # Subquery to get genres from tracks
        stmt_track = select(func.unnest(TrackModel.genres).label("genre")).where(TrackModel.user_id == user_id)
        if provider is not None:
            stmt_track = stmt_track.where(TrackModel.provider == provider)

        # Combine both and get distinct sorted values
        combined = stmt_artist.union(stmt_track).subquery()

        stmt = select(combined.c.genre).distinct().where(combined.c.genre.isnot(None)).order_by(combined.c.genre)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[list[uuid.UUID], int]:
        return await bulk_item_upsert(
            session=self.session,
            sql_model=TrackModel,
            items=tracks,
            batch_size=batch_size,
        )

    async def purge(self, user_id: uuid.UUID, provider: MusicProvider, sources: TrackSource | None = None) -> int:
        # Full delete
        if sources is None:
            stmt = delete(TrackModel).where(TrackModel.user_id == user_id, TrackModel.provider == provider)
            result = await self.session.execute(stmt)
            return int(result.rowcount)  # type: ignore

        # Otherwise, clear the requested bits from all matching rows first
        await self.session.execute(
            update(TrackModel)
            .where(TrackModel.user_id == user_id, TrackModel.provider == provider)
            .where(TrackModel.sources.op("&")(int(sources)) != 0)
            .values(sources=TrackModel.sources.op("&")(~int(sources)))
        )

        # Then delete rows that now have no sources left
        result = await self.session.execute(
            delete(TrackModel)
            .where(TrackModel.user_id == user_id, TrackModel.provider == provider)
            .where(TrackModel.sources == 0)
            .returning(TrackModel.id)
        )
        return len(result.all())


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
        excluded = stmt.excluded

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_={
                # Accumulates sources with bitwise OR; keeps latest played_at; overrides everything else.
                key: (
                    sql_model.sources.bitwise_or(excluded["sources"])
                    if key == "sources"
                    else func.greatest(getattr(sql_model, key), excluded[key])
                    if key == "played_at"
                    else excluded[key]
                )
                for key in items_chunk[0]
                if key not in index_excluded
            },
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
