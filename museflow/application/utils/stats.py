from museflow.domain.enums import RankingSortBy
from museflow.domain.utils.stats import compute_overall
from museflow.domain.utils.stats import compute_quality
from museflow.domain.value_objects.stats import RankableStats
from museflow.domain.value_objects.stats import Ranking


def rank_stats[S: RankableStats](
    all_stats: list[S],
    global_mean: float,
    confidence: int,
    sort: RankingSortBy,
    limit: int,
) -> list[Ranking[S]]:
    rankings: list[Ranking[S]] = []
    for stats in all_stats:
        rate_avg = stats.rated_sum / stats.rated_count if stats.rated_count else None
        quality = compute_quality(rate_avg, stats.rated_count, global_mean, confidence)
        rankings.append(
            Ranking(
                stats=stats,
                quality_score=quality if rate_avg is not None else None,
                overall_score=compute_overall(stats.track_count, stats.plays_count, quality, global_mean),
                rate_avg=rate_avg,
            )
        )

    if sort == RankingSortBy.TRACK_COUNT:
        rankings.sort(key=lambda r: (-r.stats.track_count, r.stats.name))
    elif sort == RankingSortBy.PLAYS_COUNT:
        rankings.sort(key=lambda r: (-r.stats.plays_count, r.stats.name))
    elif sort == RankingSortBy.RATE_AVG:
        rankings.sort(key=lambda r: (-(r.rate_avg or 0.0), r.stats.name))
    elif sort == RankingSortBy.QUALITY:
        rankings.sort(key=lambda r: (-(r.quality_score or 0.0), r.stats.name))
    else:
        rankings.sort(key=lambda r: (-r.overall_score, r.stats.name))

    return rankings[:limit]
