import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.auth import OAuthProviderUserTokenCreate
from museflow.domain.entities.auth import OAuthProviderUserTokenUpdate
from museflow.domain.entities.music import MusicProvider


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


class OAuthProviderTokenRepositoryPort(ABC):
    @abstractmethod
    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None: ...

    @abstractmethod
    async def create(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenCreate,
    ) -> OAuthProviderUserToken | None: ...

    @abstractmethod
    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenUpdate,
    ) -> OAuthProviderUserToken: ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None: ...
