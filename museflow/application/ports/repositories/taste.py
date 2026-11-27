import uuid
from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.value_objects.taste import TasteProfileData


class TasteProfileRepository(ABC):
    @abstractmethod
    async def get_list(self, user_id: uuid.UUID, limit: int | None = None, offset: int = 0) -> list[TasteProfile]:
        """Return the user's profiles, the last updated first. `limit` and `offset` page them; no limit returns them all."""
        ...

    @abstractmethod
    async def count(self, user_id: uuid.UUID) -> int: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, name: str) -> TasteProfile | None: ...

    @abstractmethod
    async def get_latest(self, user_id: uuid.UUID) -> TasteProfile | None: ...

    @abstractmethod
    async def upsert(self, profile: TasteProfile) -> TasteProfile: ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, name: str) -> bool: ...

    @abstractmethod
    async def upsert_checkpoint(
        self,
        user_id: uuid.UUID,
        name: str,
        logic_version: str,
        profiler_metadata: dict[str, Any],
        tracks_count: int,
        profile_data: TasteProfileData,
        batch_index: int,
    ) -> None: ...

    @abstractmethod
    async def get_checkpoint(self, user_id: uuid.UUID, name: str) -> tuple[TasteProfileData, int] | None: ...
