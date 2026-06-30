import dataclasses
import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.track import Track
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.types import GenreTag
from museflow.domain.types import MoodTag
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackOrdering
from museflow.domain.types import TrackSource
from museflow.domain.value_objects.track import TrackKnowIdentifiers
from museflow.infrastructure.adapters.database.models import Track as TrackModel


class TrackSQLRepository(TrackRepository):
    FIELDS_UPDATE_WHITELIST: dict[str, str] = {
        "genres": "genres",
        "moods": "moods",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
        provider_ids: list[str] | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        source: TrackSource | None = None,
        unrated_only: bool = False,
        exclude_skipped: bool = False,
        score_skipped_only: bool = False,
        artist_name: str | None = None,
        played_first_min: date | None = None,
        played_first_max: date | None = None,
        played_last_min: date | None = None,
        played_last_max: date | None = None,
        exclude_ids: list[uuid.UUID] | None = None,
        unenriched_only: bool = False,
        genres: list[GenreTag] | None = None,
        moods: list[MoodTag] | None = None,
        order: TrackOrdering | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        stmt = select(TrackModel).where(TrackModel.user_id == user_id)

        # Filtering
        if provider is not None:
            stmt = stmt.where(
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements(museflow_track.provider_links) AS elem "
                    "WHERE elem->>'provider' = :provider)"
                ).bindparams(provider=provider.value)
            )
        if provider_ids is not None:
            stmt = stmt.where(
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements(museflow_track.provider_links) AS elem "
                    "WHERE elem->>'provider_id' = ANY(:provider_ids))"
                ).bindparams(provider_ids=provider_ids)
            )
        if min_score is not None:
            stmt = stmt.where(TrackModel.score >= min_score)
        if max_score is not None:
            stmt = stmt.where(TrackModel.score <= max_score)
        if source is not None:
            stmt = stmt.where(TrackModel.source.op("&")(int(source)) != 0)
        if unrated_only:
            stmt = stmt.where(TrackModel.score.is_(None))
        if exclude_skipped:
            stmt = stmt.where(TrackModel.score_skipped.is_(False))
        if score_skipped_only:
            stmt = stmt.where(TrackModel.score_skipped.is_(True))
        if artist_name is not None:
            stmt = stmt.where(func.lower(TrackModel.artists[0].as_string()) == artist_name.lower())
        if played_first_min is not None:
            stmt = stmt.where(func.date(TrackModel.played_at_first) >= played_first_min)
        if played_first_max is not None:
            stmt = stmt.where(func.date(TrackModel.played_at_first) <= played_first_max)
        if played_last_min is not None:
            stmt = stmt.where(func.date(TrackModel.played_at_last) >= played_last_min)
        if played_last_max is not None:
            stmt = stmt.where(func.date(TrackModel.played_at_last) <= played_last_max)
        if exclude_ids:
            stmt = stmt.where(TrackModel.id.notin_(exclude_ids))
        if unenriched_only:
            stmt = stmt.where(func.array_length(TrackModel.genres, 1).is_(None))
        if genres is not None:
            stmt = stmt.where(TrackModel.genres.overlap([g.value for g in genres]))
        if moods is not None:
            stmt = stmt.where(TrackModel.moods.overlap([m.value for m in moods]))

        # Ordering
        if order is None and min_score is not None:
            stmt = stmt.order_by(TrackModel.score.desc().nulls_last())
        else:
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

    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[list[uuid.UUID], int]:
        track_ids: list[uuid.UUID] = []
        created_count: int = 0

        index_elements: list[str] = ["user_id", "fingerprint"]
        # score_skipped, genres, moods excluded so re-imports never overwrite user decisions/enrichment
        index_excluded: list[str] = ["id", "score_skipped", "genres", "moods"] + index_elements

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
                        func.greatest(getattr(TrackModel, key), excluded[key])
                        if key == "played_at_last"
                        else func.least(
                            func.coalesce(getattr(TrackModel, key), excluded[key]),
                            func.coalesce(excluded[key], getattr(TrackModel, key)),
                        )
                        if key == "played_at_first"
                        else getattr(TrackModel, key).op("|")(excluded[key])
                        if key == "source"
                        else func.coalesce(getattr(TrackModel, key), excluded[key])
                        if key == "score"
                        else TrackModel.provider_links.op("||")(excluded[key])
                        if key == "provider_links"
                        else excluded[key]
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

    async def bulk_update(self, tracks: list[Track], fields: set[str]) -> None:
        if not tracks:
            return

        unknown = fields - self.FIELDS_UPDATE_WHITELIST.keys()
        if unknown:
            raise ValueError(f"Unknown track fields: {unknown}")

        await self.session.execute(
            update(TrackModel),
            [{"id": t.id, **{self.FIELDS_UPDATE_WHITELIST[f]: getattr(t, f) for f in fields}} for t in tracks],
        )
        await self.session.commit()

    async def rate(self, user_id: uuid.UUID, track_id: uuid.UUID, score: int) -> None:
        stmt = (
            update(TrackModel)
            .where(TrackModel.id == track_id, TrackModel.user_id == user_id)
            .values(score=score)
            .returning(TrackModel.id)
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise TrackNotFoundError()
        await self.session.commit()

    async def skip(self, user_id: uuid.UUID, track_id: uuid.UUID) -> None:
        stmt = (
            update(TrackModel)
            .where(TrackModel.id == track_id, TrackModel.user_id == user_id)
            .values(score_skipped=True)
            .returning(TrackModel.id)
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise TrackNotFoundError()
        await self.session.commit()

    async def reset_score(self, user_id: uuid.UUID, source: TrackSource) -> int:
        stmt = (
            update(TrackModel)
            .where(TrackModel.user_id == user_id)
            .where(TrackModel.source.op("&")(int(source)) != 0)
            .values(score=None)
            .returning(TrackModel.id)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return len(result.scalars().all())

    async def delete(
        self,
        user_id: uuid.UUID,
        artist_name: str | None = None,
        track_name: str | None = None,
        source: TrackSource | None = None,
        provider: MusicProvider | None = None,
    ) -> int:
        if provider is not None:
            return await self._strip_provider_and_delete_empty(user_id=user_id, provider=provider)

        stmt = delete(TrackModel).where(TrackModel.user_id == user_id)

        if artist_name is not None:
            stmt = stmt.where(func.lower(TrackModel.artists[0].as_string()) == artist_name.lower())
        if track_name is not None:
            stmt = stmt.where(func.lower(TrackModel.name) == track_name.lower())
        if source is not None:
            stmt = stmt.where(TrackModel.source.op("&")(int(source)) != 0)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return int(result.rowcount)  # type: ignore

    async def purge(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        return await self._strip_provider_and_delete_empty(user_id=user_id, provider=provider)

    async def _strip_provider_and_delete_empty(self, user_id: uuid.UUID, provider: MusicProvider) -> int:
        # Step 1: Remove provider link from all tracks that have it
        await self.session.execute(
            text("""
                UPDATE museflow_track
                SET provider_links = (
                    SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                    FROM jsonb_array_elements(provider_links) AS elem
                    WHERE elem->>'provider' != :provider
                )
                WHERE user_id = :user_id
                  AND EXISTS (
                      SELECT 1 FROM jsonb_array_elements(provider_links) AS elem
                      WHERE elem->>'provider' = :provider
                  )
            """).bindparams(user_id=user_id, provider=provider.value)
        )

        # Step 2: Delete tracks now left with no provider links
        delete_stmt = delete(TrackModel).where(
            TrackModel.user_id == user_id,
            func.jsonb_array_length(TrackModel.provider_links) == 0,
        )
        result = await self.session.execute(delete_stmt)

        await self.session.commit()
        return int(result.rowcount)  # type: ignore
