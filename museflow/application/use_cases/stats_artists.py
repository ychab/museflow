import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.utils.stats import compute_overall
from museflow.domain.utils.stats import compute_quality
from museflow.domain.value_objects.stats import ArtistRanking


async def get_top_artists(
    user_id: uuid.UUID,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: ArtistSortBy,
    limit: int,
    uow: UnitOfWorkPort,
) -> list[ArtistRanking]:
    async with uow:
        all_stats = await uow.tracks.get_artist_stats(
            user_id=user_id,
            source=source.to_track_source(),
            score_min=score_min,
            score_max=score_max,
        )

    # Each track has one primary artist: their stats add up to the whole library
    rated_count_total = sum(stats.rated_count for stats in all_stats)
    global_mean = sum(stats.rated_sum for stats in all_stats) / rated_count_total if rated_count_total else 0.0

    rows: list[ArtistRanking] = []
    for stats in all_stats:
        rate_avg = stats.rated_sum / stats.rated_count if stats.rated_count else None
        quality = compute_quality(rate_avg, stats.rated_count, global_mean, confidence)
        rows.append(
            ArtistRanking(
                artist=stats.artist,
                quality_score=quality if rate_avg is not None else None,
                overall_score=compute_overall(stats.track_count, stats.plays_count, quality, global_mean),
                rate_avg=rate_avg,
                rated_count=stats.rated_count,
                track_count=stats.track_count,
                plays_count=stats.plays_count,
            )
        )

    if sort == ArtistSortBy.TRACK_COUNT:
        rows.sort(key=lambda r: (-r.track_count, r.artist))
    elif sort == ArtistSortBy.PLAYS_COUNT:
        rows.sort(key=lambda r: (-r.plays_count, r.artist))
    elif sort == ArtistSortBy.RATE_AVG:
        rows.sort(key=lambda r: (-(r.rate_avg or 0.0), r.artist))
    elif sort == ArtistSortBy.QUALITY:
        rows.sort(key=lambda r: (-(r.quality_score or 0.0), r.artist))
    else:
        rows.sort(key=lambda r: (-r.overall_score, r.artist))

    return rows[:limit]
