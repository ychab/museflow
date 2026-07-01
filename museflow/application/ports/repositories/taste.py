import uuid
from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.enums import TasteProfiler


class TasteProfileRepository(ABC):
    @abstractmethod
    async def list(self, user_id: uuid.UUID) -> list[TasteProfile]: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, name: str) -> TasteProfile | None: ...

    @abstractmethod
    async def get_latest(self, user_id: uuid.UUID, profiler: TasteProfiler) -> TasteProfile | None: ...

    @abstractmethod
    async def upsert(self, profile: TasteProfile) -> TasteProfile: ...

    @abstractmethod
    async def save_checkpoint(
        self,
        user_id: uuid.UUID,
        name: str,
        profiler: TasteProfiler,
        logic_version: str,
        profiler_metadata: dict[str, Any],
        tracks_count: int,
        profile_data: TasteProfileData,
        batch_index: int,
    ) -> None: ...

    @abstractmethod
    async def get_checkpoint(self, user_id: uuid.UUID, name: str) -> tuple[TasteProfileData, int] | None: ...
