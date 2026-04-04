import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import UserTasteProfile
from museflow.domain.types import MusicAdvisor


class TasteProfileRepository(ABC):
    @abstractmethod
    async def upsert(self, profile: UserTasteProfile) -> UserTasteProfile: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, advisor: MusicAdvisor) -> UserTasteProfile | None: ...
