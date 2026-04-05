import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.types import TasteProfiler


class TasteProfileRepository(ABC):
    @abstractmethod
    async def upsert(self, profile: TasteProfile) -> TasteProfile: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, profiler: TasteProfiler) -> TasteProfile | None: ...
