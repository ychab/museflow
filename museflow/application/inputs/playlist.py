from dataclasses import dataclass
from dataclasses import field
from datetime import date

from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import PlaylistHistoryOrderBy
from museflow.domain.types import LocaleCode


@dataclass(frozen=True, kw_only=True)
class PlaylistHistoryConfigInput:
    name_suffix: str | None = None
    score_min: int | None = None
    score_max: int | None = None
    artist_name: str | None = None
    genres: list[GenreTag] = field(default_factory=list)
    moods: list[MoodTag] = field(default_factory=list)
    locales: list[LocaleCode] = field(default_factory=list)
    played_first_min: date | None = None
    played_first_max: date | None = None
    played_last_min: date | None = None
    played_last_max: date | None = None
    allow_duplicate: bool = False
    group_by_artists: bool = False
    dry_run: bool = False
    sort_by: PlaylistHistoryOrderBy = PlaylistHistoryOrderBy.PLAYED_COUNT
    limit: int = 20
