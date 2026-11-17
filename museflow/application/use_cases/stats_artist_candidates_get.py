import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.enums import SourceFilter
from museflow.domain.value_objects.stats import ArtistCandidate


async def get_artist_candidates(
    user_id: uuid.UUID,
    source: SourceFilter,
    max_tracks: int,
    min_avg: float,
    limit: int,
    uow: UnitOfWorkPort,
) -> list[ArtistCandidate]:
    async with uow:
        all_stats = await uow.tracks.get_artist_stats(user_id=user_id, source=source.to_track_source())

    rows: list[ArtistCandidate] = []
    for stats in all_stats:
        if stats.track_count > max_tracks or stats.rated_count == 0:
            continue

        avg_score = stats.rated_sum / stats.rated_count
        if avg_score < min_avg:
            continue

        rows.append(
            ArtistCandidate(
                artist=stats.artist,
                avg_score=avg_score,
                rated_count=stats.rated_count,
                total_count=stats.track_count,
            )
        )

    rows.sort(key=lambda r: (-r.avg_score, r.artist))
    return rows[:limit]
