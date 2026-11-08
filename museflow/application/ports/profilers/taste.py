from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.value_objects.llm import LLMUsage
from museflow.domain.value_objects.taste import ListeningPeriod


class TasteProfilerPort(ABC):
    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def logic_version(self) -> str: ...

    @property
    @abstractmethod
    def profiler_metadata(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def usages(self) -> list[LLMUsage]:
        """Tokens and cost of the calls made since the adapter was created, per step and model."""
        ...

    @abstractmethod
    async def build_profile_segment(self, period: ListeningPeriod) -> TasteProfileData:
        """Analyze the tracks most played during a listening period and return a partial taste profile."""

    @abstractmethod
    async def merge_profiles(
        self,
        foundation: TasteProfileData,
        new_segment: TasteProfileData,
        segment_weight: float,
    ) -> TasteProfileData:
        """Merge new_segment into the existing foundation profile.

        Args:
            segment_weight: the segment's share of the core identity, between 0 and 1.
        """

    @abstractmethod
    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        """Final psychographic pass."""

    @abstractmethod
    async def close(self) -> None: ...
