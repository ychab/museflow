import uuid
from typing import cast

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import TrackSortBy


async def list_top_tracks(
    user_id: uuid.UUID,
    score_min: int | None,
    score_max: int | None,
    sort: TrackSortBy,
    limit: int,
    uow: UnitOfWorkPort,
) -> list[Track]:
    async with uow:
        tracks = await uow.tracks.list(
            user_id=user_id,
            min_score=score_min if score_min is not None else 0,
            max_score=score_max,
            limit=None,
        )

    if sort == TrackSortBy.PLAYED_COUNT:
        tracks.sort(key=lambda t: (-t.played_count, t.artists[0] if t.artists else ""))
    else:
        tracks.sort(key=lambda t: (-cast(int, t.score), t.artists[0] if t.artists else ""))

    return tracks[:limit]
