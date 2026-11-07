import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track


async def export_enrichment(
    user_id: uuid.UUID,
    uow: UnitOfWorkPort,
) -> list[Track]:
    async with uow:
        tracks = await uow.tracks.list(user_id=user_id)

    # Empty locales still count: the track was enriched as instrumental.
    return [track for track in tracks if track.genres or track.moods or track.locales is not None]
