from dataclasses import dataclass

from museflow.domain.types import PlaylistHistoryOrderBy


@dataclass(frozen=True, kw_only=True)
class PlaylistHistoryConfigInput:
    score_min: int | None = None
    score_max: int | None = None
    artist_name: str | None = None
    allow_duplicate: bool = False
    group_by_artists: bool = False
    sort_by: PlaylistHistoryOrderBy = PlaylistHistoryOrderBy.PLAYED_COUNT
    limit: int = 20
