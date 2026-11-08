import dataclasses
import itertools
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import LateralFromClause

from museflow.application.ports.repositories.track_play import TrackPlayRepository
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
