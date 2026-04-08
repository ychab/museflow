from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.types import TasteProfiler


class TasteProfilerPort(ABC):
    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def profiler_type(self) -> TasteProfiler: ...

    @property
    @abstractmethod
    def logic_version(self) -> str: ...

    @property
    @abstractmethod
    def profiler_metadata(self) -> dict[str, Any]: ...

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
