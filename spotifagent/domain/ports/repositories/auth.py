import uuid
from abc import ABC
from abc import abstractmethod

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.music import MusicProvider


class OAuthProviderStateRepositoryPort(ABC):
    @abstractmethod
    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        state: str,
    ) -> tuple[OAuthProviderState, bool]: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderState | None: ...

    @abstractmethod
    async def consume(self, state: str) -> OAuthProviderState | None: ...
