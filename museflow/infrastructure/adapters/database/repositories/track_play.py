import dataclasses
import itertools
import uuid
from typing import Final

from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import LateralFromClause

from museflow.application.ports.repositories.track_play import TrackPlayRepository
from museflow.domain.value_objects.taste import ListeningPeriod
from museflow.domain.value_objects.taste import PeriodTrack
from museflow.domain.value_objects.track import TrackPlay
from museflow.infrastructure.adapters.database.models.track import Track as TrackModel
from museflow.infrastructure.adapters.database.models.track import TrackPlay as TrackPlayModel


class TrackPlaySQLRepository(TrackPlayRepository):
    # asyncpg refuses a statement with more parameters than this; a play takes 2 (track, time, the id coming from the
    # database), so a chunk holds as many plays as fit.
    _MAX_PARAMETERS: Final[int] = 32_767
    _CHUNK_SIZE: Final[int] = _MAX_PARAMETERS // 2

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def plays_summary() -> LateralFromClause:
        """The play data of each track a query loads: `played_count`, `played_at_first` and `played_at_last`.

        Shared with the repositories that load tracks (tracks, playlists): a track has no play column, so each of
        their queries joins this subquery with `.join(plays, true())` and passes its three columns to
        `Track.to_entity`, which requires them.

        PostgreSQL runs this LATERAL subquery once per track row, with that row's `museflow_track.id` in scope: one
        pass over the track's plays in the `(track_id, played_at)` index gives the three values, without reading the
        table (index-only scan). Unlike a join on plays grouped by track, it only computes the tracks the query loads,
        whatever the number of plays of the other users. An aggregate without GROUP BY always returns one row, so a
        track without plays keeps its row, with a count of 0 and no dates.
        """
        return (
            select(
                # count(*), not count(id): the id is not in the index, which would send every count to the table
                func.count().label("played_count"),
                func.min(TrackPlayModel.played_at).label("played_at_first"),
                func.max(TrackPlayModel.played_at).label("played_at_last"),
            )
            .where(TrackPlayModel.track_id == TrackModel.id)
            .lateral("plays")
        )

    async def bulk_create(self, plays: list[TrackPlay]) -> int:
        created = 0
        for chunk in itertools.batched(plays, self._CHUNK_SIZE, strict=False):
            stmt = (
                pg_insert(TrackPlayModel)
                .values([dataclasses.asdict(play) for play in chunk])
                .on_conflict_do_nothing(index_elements=["track_id", "played_at"])
                .returning(TrackPlayModel.id)
            )
            created += len((await self.session.execute(stmt)).all())
        return created

    async def count_played_tracks(self, user_id: uuid.UUID, min_score: int | None = None) -> int:
        stmt = (
            select(func.count(distinct(TrackPlayModel.track_id)))
            .join(TrackModel, TrackModel.id == TrackPlayModel.track_id)
            .where(TrackModel.user_id == user_id)
        )
        if min_score is not None:
            stmt = stmt.where(TrackModel.score >= min_score)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_periods(
        self,
        user_id: uuid.UUID,
        periods: int,
        tracks_per_period: int,
        min_score: int | None = None,
    ) -> list[ListeningPeriod]:
        # 1. The user's plays, each numbered with its period: ntile() deals them out, oldest first, into `periods`
        #    groups of the same size.
        user_plays = (
            select(
                TrackPlayModel.track_id,
                TrackPlayModel.played_at,
                func.ntile(periods).over(order_by=TrackPlayModel.played_at).label("period"),
            )
            .join(TrackModel, TrackModel.id == TrackPlayModel.track_id)
            .where(TrackModel.user_id == user_id)
        )
        if min_score is not None:
            user_plays = user_plays.where(TrackModel.score >= min_score)
        plays = user_plays.cte("plays")

        # 2. Each period's first and last play and its number of plays.
        bounds = (
            select(
                plays.c.period,
                func.min(plays.c.played_at).label("start"),
                func.max(plays.c.played_at).label("end"),
                func.count().label("plays"),
            )
            .group_by(plays.c.period)
            .cte("bounds")
        )

        # 3. The plays of each track in each period, ranked within the period: most played first.
        track_plays = (
            select(plays.c.period, plays.c.track_id, func.count().label("plays"))
            .group_by(plays.c.period, plays.c.track_id)
            .cte("track_plays")
        )
        ranked = select(
            track_plays,
            func.row_number()
            .over(
                partition_by=track_plays.c.period,
                order_by=(track_plays.c.plays.desc(), track_plays.c.track_id),
            )
            .label("rank"),
        ).cte("ranked")

        # 4. The top tracks of each period, with their period, and their play data over the whole history.
        summary = self.plays_summary()
        stmt = (
            select(
                ranked.c.period,
                ranked.c.plays,
                bounds.c.start,
                bounds.c.end,
                bounds.c.plays.label("period_plays"),
                TrackModel,
                summary.c.played_count,
                summary.c.played_at_first,
                summary.c.played_at_last,
            )
            .join(bounds, bounds.c.period == ranked.c.period)
            .join(TrackModel, TrackModel.id == ranked.c.track_id)
            .join(summary, true())
            .where(ranked.c.rank <= tracks_per_period)
            .order_by(ranked.c.period, ranked.c.rank)
        )

        listening_periods: dict[int, ListeningPeriod] = {}
        for row in (await self.session.execute(stmt)).all():
            listening_period = listening_periods.setdefault(
                row.period,
                ListeningPeriod(start=row.start, end=row.end, plays=row.period_plays, tracks=[]),
            )
            track = row.Track.to_entity(
                played_count=row.played_count,
                played_at_first=row.played_at_first,
                played_at_last=row.played_at_last,
            )
            listening_period.tracks.append(PeriodTrack(track=track, plays=row.plays))
        return list(listening_periods.values())
