import uuid
from dataclasses import dataclass

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.stats import rank_stats
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTier
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.types import TagRanking


@dataclass(frozen=True, kw_only=True)
class TopTagsResult:
    rankings: list[TagRanking]
    unenriched_count: int  # tracks without any tag of the field, left out of the rankings


async def get_top_tags(
    user_id: uuid.UUID,
    field: EnrichField,
    tier: GenreTier | None,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: RankingSortBy,
    limit: int,
    uow: UnitOfWorkPort,
) -> TopTagsResult:
    async with uow:
        all_stats = await uow.tracks.get_tag_stats(
            user_id=user_id,
            field=field,
            tier=tier,
            source=source.to_track_source(),
            score_min=score_min,
            score_max=score_max,
        )
        # The whole library is the reference, as for the artists: a track counts in several tags, or in none
        library_stats = await uow.tracks.get_library_stats(
            user_id=user_id,
            field=field,
            source=source.to_track_source(),
            score_min=score_min,
            score_max=score_max,
        )

    rankings = rank_stats(
        all_stats,
        global_mean=library_stats.rate_avg,
        confidence=confidence,
        sort=sort,
        limit=limit,
    )
    return TopTagsResult(rankings=rankings, unenriched_count=library_stats.unenriched_count)
