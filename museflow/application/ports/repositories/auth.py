import uuid
from abc import ABC
from abc import abstractmethod

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider


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

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None:
        """Deletes the OAuth state of a user and provider, if any, when a flow is given up.

        Args:
            user_id: The user's ID.
            provider: The music provider.
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
    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenCreateInput,
    ) -> OAuthProviderUserToken:
        """Creates the auth token of a user and provider, or replaces the one already there.

        One statement: two OAuth callbacks of the same user at once can't both create it.

        Args:
            user_id: The user's ID.
            provider: The music provider.
            auth_token_in: A schema object with the token data.

        Returns:
            The created or replaced `OAuthProviderUserToken` entity.
        """
        ...

    @abstractmethod
    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenUpdateInput,
        expected_token_access: str,
    ) -> OAuthProviderUserToken | None:
        """Updates the auth token of a user and provider, only if it still holds the expected access token.

        A compare-and-swap for the token refresh: every refresh or reconnect issues a new access token, so a stored
        token whose access token changed was replaced by another session meanwhile, and its newer value is kept.

        Args:
            user_id: The user's ID.
            provider: The music provider.
            auth_token_in: A schema object with the updated token data.
            expected_token_access: The access token the update replaces.

        Returns:
            The updated `OAuthProviderUserToken` entity, or None if the stored token no longer holds
            `expected_token_access` or is gone.
        """
        ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, provider: MusicProvider, expected_token_refresh: str) -> bool:
        """Deletes the auth token of a user and provider, only if it still holds the expected refresh token.

        Used when the provider rejects the refresh token: a token another session refreshed or reconnected
        meanwhile holds another refresh token, and is kept.

        Args:
            user_id: The user's ID.
            provider: The music provider.
            expected_token_refresh: The refresh token the provider rejected.

        Returns:
            True if the token was deleted, False if the stored token changed meanwhile or is gone.
        """
        ...
