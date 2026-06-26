from pydantic import BaseModel
from pydantic import Field

from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN


class RateEntryInput(BaseModel):
    fingerprint: str
    score: int | None = Field(default=None, ge=DISCOVERY_TRACK_SCORE_MIN, le=DISCOVERY_TRACK_SCORE_MAX)
    score_skipped: bool = False
