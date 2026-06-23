from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PlaylistHistoryConfigInput:
    score_min: int | None = None
    score_max: int | None = None
    artist_name: str | None = None
    limit: int = 20
    allow_duplicate: bool = False
