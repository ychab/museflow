from abc import ABC
from abc import abstractmethod

from pydantic import HttpUrl

from museflow.domain.value_objects.auth import OAuthProviderTokenPayload


class ProviderClientPort(ABC):
    """A port defining the contract for a stateless OAuth client for a music provider.

    This interface abstracts the details of interacting with a provider's OAuth2
    endpoints, ensuring that the application's domain logic remains decoupled from
    specific provider implementations. It handles URL generation, token exchange,
    and token refresh.
    """

    @abstractmethod
    def get_authorization_url(self, state: str) -> HttpUrl:
        """Generates the provider's OAuth authorization URL.

        Args:
            state: A unique string to prevent CSRF attacks.

        Returns:
            The full authorization URL to redirect the user to.
        """
        ...

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> OAuthProviderTokenPayload:
        """Exchanges an authorization code for an access token.

        Args:
            code: The authorization code received from the provider's callback.

        Returns:
            A payload containing the access token, refresh token, and expiry information.
        """
        ...

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> OAuthProviderTokenPayload:
        """Refreshes an expired access token using a refresh token.

        Args:
            refresh_token: The refresh token associated with the user's authorization.

        Returns:
            A payload containing the new access token and its expiry information.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the client and cleans up any underlying resources, like HTTP sessions."""
        ...
