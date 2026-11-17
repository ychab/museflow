import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.stats import rank_stats
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.types import ArtistRanking


async def get_top_artists(
    user_id: uuid.UUID,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: RankingSortBy,
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

    return rank_stats(all_stats, global_mean=global_mean, confidence=confidence, sort=sort, limit=limit)
