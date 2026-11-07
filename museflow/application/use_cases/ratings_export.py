import uuid
from dataclasses import dataclass

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.entities.track import Track


@dataclass(frozen=True, kw_only=True)
class RatingsExport:
    rated: list[Track]
    skipped: list[Track]


async def export_ratings(
    user_id: uuid.UUID,
    uow: UnitOfWorkPort,
) -> RatingsExport:
    async with uow:
        rated = await uow.tracks.list(user_id=user_id, min_score=DISCOVERY_TRACK_SCORE_MIN)
        skipped = await uow.tracks.list(user_id=user_id, score_skipped_only=True)

    return RatingsExport(rated=rated, skipped=skipped)
