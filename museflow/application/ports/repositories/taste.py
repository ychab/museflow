import uuid
from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData


class TasteProfileRepository(ABC):
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

    # Last in the class: below this method, `list` in an annotation would name it, not the builtin.
    @abstractmethod
    async def list(self, user_id: uuid.UUID) -> list[TasteProfile]: ...
