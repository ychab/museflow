from pydantic import BaseModel
from pydantic import Field

from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.entities.track import ProviderLink
from museflow.domain.enums import TrackSource


class RatingEntryInput(BaseModel):
    fingerprint: str
    score: int | None = Field(default=None, ge=DISCOVERY_TRACK_SCORE_MIN, le=DISCOVERY_TRACK_SCORE_MAX)
    score_skipped: bool = False

    # What recreates the track when the library lacks it (e.g. a discovery never played, after a reset).
    # Optional: an entry without them only rates a track already in the library.
    name: str | None = None
    artists: list[str] = []
    album_name: str | None = None
    source: TrackSource = TrackSource.HISTORY
    provider_links: list[ProviderLink] = []
