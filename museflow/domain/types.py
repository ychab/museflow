from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.value_objects.stats import ArtistStats
from museflow.domain.value_objects.stats import Ranking
from museflow.domain.value_objects.stats import TagStats

type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]
type LocaleCode = str  # ISO 639-1 two-letter lowercase language code, e.g. "fr", "en"
type ArtistRanking = Ranking[ArtistStats]
type TagRanking = Ranking[TagStats]
