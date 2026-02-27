import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate
from museflow.domain.types import MusicProvider


class OAuthProviderStateRepository(ABC):
    """A repository for managing `OAuthProviderState` entities.

    This repository handles the storage and retrieval of state tokens used during
    the OAuth authorization flow to prevent CSRF attacks.
    """

    @abstractmethod
    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        state: str,
    ) -> tuple[OAuthProviderState, bool]:
        """Creates or updates an OAuth state for a given user and provider.

        Args:
            user_id: The ID of the user initiating the authorization.
            provider: The music provider being authorized.
            state: The unique state string to be stored.

        Returns:
            A tuple containing the `OAuthProviderState` entity and a boolean
            indicating whether the entity was created (True) or updated (False).
        """
        ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderState | None:
        """Retrieves the current OAuth state for a user and provider.

        Args:
            user_id: The user's ID.
            provider: The music provider.

        Returns:
            The `OAuthProviderState` entity if one exists, otherwise None.
        """
        ...

    @abstractmethod
    async def consume(self, state: str) -> OAuthProviderState | None:
        """Retrieves and then deletes an OAuth state, marking it as used.

        This is a critical step to prevent replay attacks by ensuring a state
        can only be used once.

        Args:
            state: The state string received from the provider's callback.

        Returns:
            The `OAuthProviderState` entity if it existed, otherwise None.
        """
        ...


class OAuthProviderTokenRepository(ABC):
    """A repository for managing `OAuthProviderUserToken` entities.

    This repository handles the persistence of user tokens required to make
    authenticated API calls to music providers.
    """

    @abstractmethod
    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None:
        """Retrieves a user's auth token for a specific provider.

        Args:
            user_id: The user's ID.
            provider: The music provider.

        Returns:
            The `OAuthProviderUserToken` if it exists, otherwise None.
        """
        ...

    @abstractmethod
    async def create(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenCreate,
    ) -> OAuthProviderUserToken | None:
        """Creates and stores a new auth token for a user and provider.

        Args:
            user_id: The user's ID.
            provider: The music provider.
            auth_token_data: A schema object with the new token data.

        Returns:
            The newly created `OAuthProviderUserToken` entity.
        """
        ...

    @abstractmethod
    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenUpdate,
    ) -> OAuthProviderUserToken:
        """Updates an existing auth token for a user and provider.

        This is typically used when refreshing an access token.

        Args:
            user_id: The user's ID.
            provider: The music provider.
            auth_token_data: A schema object with the updated token data.

        Returns:
            The updated `OAuthProviderUserToken` entity.
        """
        ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None:
        """Deletes a user's auth token for a provider.

        This is used when a user revokes access to the application.

        Args:
            user_id: The user's ID.
            provider: The music provider.
        """
        ...
