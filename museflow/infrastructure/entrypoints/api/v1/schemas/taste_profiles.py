import uuid
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from museflow.domain.enums import TasteProfileStatus


class TechnicalFingerprintResponse(BaseModel):
    energy: float
    acousticness: float
    rhythmic_complexity: float
    atmospheric: float
    instrumentalness: float


class TasteEraResponse(BaseModel):
    era_label: str
    time_range: str
    technical_fingerprint: TechnicalFingerprintResponse
    dominant_moods: list[str]


class TasteProfileDataResponse(BaseModel):
    taste_timeline: list[TasteEraResponse] = Field(description="The eras of the listening history, the latest first")
    core_identity: dict[str, float] = Field(description="The genres of the whole history, weighted")
    current_vibe: dict[str, float] = Field(description="The genres of the latest listening, weighted")
    personality_archetype: str | None
    life_phase_insights: list[str]
    musical_identity_summary: str | None
    behavioral_traits: dict[str, float]
    discovery_style: str | None


class TasteProfileSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(description="The slug keying the profile in the URLs")
    title: str = Field(description="What to show, as the user typed it")
    status: TasteProfileStatus = Field(
        description="`building` while a build runs or is paused: the profile is partial"
    )
    tracks_count: int = Field(description="The tracks the profile was built from")
    logic_version: str = Field(description="The version of the build logic: a profile built by an older one is stale")
    created_at: datetime
    updated_at: datetime


class TasteProfileResponse(TasteProfileSummaryResponse):
    profile: TasteProfileDataResponse
