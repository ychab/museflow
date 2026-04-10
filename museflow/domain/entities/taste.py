import re
import uuid
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from typing import Any
from typing import TypedDict

from museflow.domain.types import TasteProfiler


class TechnicalFingerprint(TypedDict):
    energy: float
    acousticness: float
    rhythmic_complexity: float
    atmospheric: float
    instrumentalness: float


class TasteEra(TypedDict):
    era_label: str  # AI-generated name, e.g. "The Post-Rock Exploration"
    time_range: str  # e.g. "2021-2023"
    technical_fingerprint: TechnicalFingerprint
    dominant_moods: list[str]


class TasteProfileData(TypedDict):
    taste_timeline: list[TasteEra]  # chronological map of taste eras
    core_identity: dict[str, float]  # stable DNA, e.g. {"progressive metal": 0.8}
    current_vibe: dict[str, float]  # active trajectory (last ~400 tracks)

    # Populated by final psychographic reflection only
    personality_archetype: str | None
    life_phase_insights: list[str]

    # Populated by final psychographic reflection only
    musical_identity_summary: str | None  # 2-3 sentence narrative of the listener's evolution
    behavioral_traits: dict[str, float]  # e.g. {"openness": 0.9, "rhythmic_dependency": 0.7}
    discovery_style: str | None  # e.g. "The Digger" or "The Loyalist"


@dataclass(frozen=True, kw_only=True)
class TasteProfile:
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    name: str
    user_id: uuid.UUID
    profiler: TasteProfiler

    profile: TasteProfileData

    profiler_metadata: dict[str, Any]
    tracks_count: int
    logic_version: str

    created_at: datetime
    updated_at: datetime

    def sort_timeline(self) -> "TasteProfile":
        def _key(era: TasteEra) -> str:
            time_range = era["time_range"]
            if "Contemporary" in time_range:
                return "9999-99-99"
            if "Undated" in time_range or "unknown" in time_range:
                return "0000-00-00"
            match = re.search(r"(\d{4}-\d{2}-\d{2})", time_range)
            return match.group(1) if match else "0000-00-00"

        sorted_timeline = sorted(self.profile["taste_timeline"], key=_key, reverse=True)
        sorted_profile: TasteProfileData = {**self.profile, "taste_timeline": sorted_timeline}
        return replace(self, profile=sorted_profile)
