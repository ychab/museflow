import dataclasses
import uuid
from datetime import date
from typing import Any

from sqlalchemy import Boolean
from sqlalchemy import Uuid
from sqlalchemy import any_
from sqlalchemy import bindparam
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import literal_column
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import true
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.types import LocaleCode
from museflow.domain.types import TrackOrdering
from museflow.domain.value_objects.track import TrackKnownIdentifiers
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.database.repositories.track_play import plays_summary


class TrackSQLRepository(TrackRepository):
    _ENRICH_FIELD_TO_COLUMN: dict[EnrichField, str] = {
        EnrichField.GENRE: "genres",
        EnrichField.MOOD: "moods",
        EnrichField.LOCALE: "locales",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_list(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider | None = None,
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
        missing_fields: frozenset[EnrichField] | None = None,
        genres: list[GenreTag] | None = None,
        moods: list[MoodTag] | None = None,
        locales: list[LocaleCode] | None = None,
        order: TrackOrdering | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[Track]:
        plays = plays_summary()
        stmt = (
            select(TrackModel, plays.c.played_count, plays.c.played_at_first, plays.c.played_at_last)
            .join(plays, true())
            .where(TrackModel.user_id == user_id)
        )

        # Filtering
        if provider is not None:
            stmt = stmt.where(
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements(museflow_track.provider_links) AS elem "
                    "WHERE elem->>'provider' = :provider)"
                ).bindparams(provider=provider.value)
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
            stmt = stmt.where(func.date(plays.c.played_at_first) >= played_first_min)
        if played_first_max is not None:
            stmt = stmt.where(func.date(plays.c.played_at_first) <= played_first_max)
        if played_last_min is not None:
            stmt = stmt.where(func.date(plays.c.played_at_last) >= played_last_min)
        if played_last_max is not None:
            stmt = stmt.where(func.date(plays.c.played_at_last) <= played_last_max)
        if exclude_ids:
            stmt = stmt.where(TrackModel.id.notin_(exclude_ids))
        if missing_fields:
            conditions = []
            if EnrichField.GENRE in missing_fields:
                conditions.append(func.array_length(TrackModel.genres, 1).is_(None))
            if EnrichField.MOOD in missing_fields:
                conditions.append(func.array_length(TrackModel.moods, 1).is_(None))
            if EnrichField.LOCALE in missing_fields:
                conditions.append(TrackModel.locales.is_(None))
            stmt = stmt.where(or_(*conditions))
        if genres is not None:
            stmt = stmt.where(TrackModel.genres.overlap([g.value for g in genres]))
        if moods is not None:
            stmt = stmt.where(TrackModel.moods.overlap([m.value for m in moods]))
        if locales is not None:
            stmt = stmt.where(TrackModel.locales.overlap(locales))

        # Ordering
        if order is None and min_score is not None:
            stmt = stmt.order_by(TrackModel.score.desc().nulls_last())
        else:
            for order_by, sort_order in order or [(TrackOrderBy.CREATED_AT, SortOrder.ASC)]:
                if order_by == TrackOrderBy.RANDOM:
                    stmt = stmt.order_by(func.random())
                    break  # RANDOM cannot be combined with further columns

                # The play data comes from the plays, the other fields from the track
                column = plays.c[order_by.value] if order_by.value in plays.c else getattr(TrackModel, order_by.value)
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

        rows = (await self.session.execute(stmt)).all()
        return [
            track_db.to_entity(played_count=played_count, played_at_first=first, played_at_last=last)
            for track_db, played_count, first, last in rows
        ]

    async def get_known_identifiers(
        self,
        user_id: uuid.UUID,
        fingerprints: list[str],
    ) -> TrackKnownIdentifiers:
        stmt = select(TrackModel.fingerprint).where(
            TrackModel.user_id == user_id,
            TrackModel.fingerprint.in_(fingerprints),
        )

        result = await self.session.execute(stmt)
        known_fingerprints = frozenset(row.fingerprint for row in result.fetchall())

        return TrackKnownIdentifiers(fingerprints=known_fingerprints)

    async def bulk_upsert(self, tracks: list[Track], batch_size: int) -> tuple[dict[str, uuid.UUID], int]:
        # Keyed by fingerprint: PostgreSQL does not guarantee that RETURNING follows the VALUES order.
        track_ids: dict[str, uuid.UUID] = {}
        created_count: int = 0

        index_elements: list[str] = ["user_id", "fingerprint"]
        # score_skipped, genres, moods, locales excluded so re-imports never overwrite user decisions/enrichment
        index_excluded: list[str] = ["id", "score_skipped", "genres", "moods", "locales"] + index_elements

        # The play data is computed from the plays, saved on their own: a track never writes it
        computed = ("played_at_first", "played_at_last", "played_count")
        tracks_dicts: list[dict[str, Any]] = [
            {key: value for key, value in dataclasses.asdict(track).items() if key not in computed} for track in tracks
        ]

        total: int = len(tracks_dicts)
        for offset in range(0, total, batch_size):
            tracks_chunk = tracks_dicts[offset : offset + batch_size]

            stmt = pg_insert(TrackModel).values(tracks_chunk)
            excluded = stmt.excluded

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_={
                    key: (
                        getattr(TrackModel, key).op("|")(excluded[key])
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
                TrackModel.fingerprint,
                TrackModel.id,
                literal_column("xmax = 0", Boolean).label("was_created"),
            )

            results = await self.session.execute(upsert_stmt)
            rows = results.all()

            track_ids.update({row.fingerprint: row.id for row in rows})
            created_count += sum(row.was_created for row in rows)

        return track_ids, created_count

    async def bulk_update(self, tracks: list[Track], fields: frozenset[EnrichField]) -> None:
        if not tracks:
            return
        columns = {self._ENRICH_FIELD_TO_COLUMN[f] for f in fields}

        await self.session.execute(
            update(TrackModel),
            [{"id": t.id, **{col: getattr(t, col) for col in columns}} for t in tracks],
        )

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

    async def reset_score(self, user_id: uuid.UUID, source: TrackSource) -> int:
        stmt = (
            update(TrackModel)
            .where(TrackModel.user_id == user_id)
            .where(TrackModel.source.op("&")(int(source)) != 0)
            .values(score=None)
            .returning(TrackModel.id)
        )

        result = await self.session.execute(stmt)

        return len(result.scalars().all())

    async def unlink_provider(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        track_ids: list[uuid.UUID] | None = None,
    ) -> list[uuid.UUID]:
        stmt = (
            update(TrackModel)
            .where(
                TrackModel.user_id == user_id,
                text(
                    "EXISTS (SELECT 1 FROM jsonb_array_elements(museflow_track.provider_links) AS elem "
                    "WHERE elem->>'provider' = :provider)"
                ).bindparams(provider=provider.value),
            )
            .values(
                provider_links=text(
                    "(SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb) "
                    "FROM jsonb_array_elements(museflow_track.provider_links) AS elem "
                    "WHERE elem->>'provider' != :provider)"
                ).bindparams(provider=provider.value)
            )
            .returning(TrackModel.id, func.jsonb_array_length(TrackModel.provider_links).label("links_left"))
        )
        if track_ids is not None:
            stmt = stmt.where(TrackModel.id == any_(bindparam("track_ids", track_ids, type_=ARRAY(Uuid))))

        result = await self.session.execute(stmt)
        return [row.id for row in result if row.links_left == 0]

    async def delete(self, user_id: uuid.UUID, track_ids: list[uuid.UUID]) -> int:
        stmt = delete(TrackModel).where(
            TrackModel.user_id == user_id, TrackModel.id == any_(bindparam("track_ids", track_ids, type_=ARRAY(Uuid)))
        )

        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore

    async def purge(self, user_id: uuid.UUID) -> int:
        stmt = delete(TrackModel).where(TrackModel.user_id == user_id)

        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore
