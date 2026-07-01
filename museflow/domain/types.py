from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy

type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]
type ScoreAdvisor = float
type ScoreReconciler = float
type LocaleCode = str  # ISO 639-1 two-letter lowercase language code, e.g. "fr", "en"
