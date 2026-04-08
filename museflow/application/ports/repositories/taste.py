import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile


class TasteProfileRepository(ABC):
    @abstractmethod
    async def upsert(self, profile: TasteProfile) -> TasteProfile: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, name: str) -> TasteProfile | None: ...
