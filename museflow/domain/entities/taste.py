import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from museflow.domain.types import TasteProfiler


class TasteEra(TypedDict):
    era_label: str  # AI-generated name, e.g. "The Post-Rock Exploration"
    time_range: str  # e.g. "2021-2023"
    technical_fingerprint: dict[str, float]  # BPM, reverb, energy (0-1 weights)
    dominant_moods: list[str]


class TasteProfileData(TypedDict):
    taste_timeline: list[TasteEra]  # chronological map of taste eras
    core_identity: dict[str, float]  # stable DNA, e.g. {"progressive metal": 0.8}
    current_vibe: dict[str, float]  # active trajectory (last ~400 tracks)
    personality_archetype: str | None  # set by final psychographic pass
    life_phase_insights: list[str]  # set by final psychographic pass


@dataclass(frozen=True, kw_only=True)
class TasteProfile:
    id: uuid.UUID
    user_id: uuid.UUID
    profiler: TasteProfiler

    profile: TasteProfileData

    tracks_count: int
    logic_version: str

    created_at: datetime
    updated_at: datetime
