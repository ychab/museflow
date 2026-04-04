from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData


class TasteProfileAdvisorPort(ABC):
    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def logic_version(self) -> str: ...

    @abstractmethod
    async def build_profile_segment(self, tracks: list[Track]) -> TasteProfileData:
        """Analyze a batch of tracks and return a partial taste profile."""

    @abstractmethod
    async def merge_profiles(self, foundation: TasteProfileData, new_segment: TasteProfileData) -> TasteProfileData:
        """Merge new_segment into the existing foundation profile."""

    @abstractmethod
    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        """Final psychographic pass: populate personality_archetype and life_phase_insights."""

    @abstractmethod
    async def close(self) -> None: ...
