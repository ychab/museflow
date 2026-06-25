from pydantic import BaseModel
from pydantic import Field

from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN


class RateEntryInput(BaseModel):
    fingerprint: str
    score: int = Field(ge=DISCOVERY_TRACK_SCORE_MIN, le=DISCOVERY_TRACK_SCORE_MAX)
