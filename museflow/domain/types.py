from typing import Literal

from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy

type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]
type LocaleCode = str  # ISO 639-1 two-letter lowercase language code, e.g. "fr", "en"
type ProviderPageErrorCodes = Literal["unsupported_local_files"]
