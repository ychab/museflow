from abc import ABC
from abc import abstractmethod
from typing import Any

from pydantic import HttpUrl

from museflow.domain.schemas.auth import OAuthProviderTokenPayload


class ProviderOAuthClientPort(ABC):
    """A port defining the contract for a stateless OAuth client for a music provider.

    This interface abstracts the details of interacting with a provider's OAuth2
    endpoints, ensuring that the application's domain logic remains decoupled from
    specific provider implementations. It handles URL generation, token exchange,
    and authenticated API calls.
    """

    @property
    @abstractmethod
    def base_url(self) -> HttpUrl:
        """The base URL for the provider's API."""
        ...

    @property
    @abstractmethod
    def token_endpoint(self) -> HttpUrl:
        """The URL for token-related operations (exchange, refresh)."""
        ...

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
    async def make_user_api_call(
        self,
        method: str,
        endpoint: str,
        token_payload: OAuthProviderTokenPayload,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Makes an authenticated API call to the provider on behalf of the user.

        Args:
            method: The HTTP method (e.g., "GET", "POST").
            endpoint: The API endpoint to call (relative to the base URL).
            token_payload: The user's token information for authentication.
            params: Optional URL query parameters.
            json_data: Optional JSON body for the request.

        Returns:
            The JSON response from the API as a dictionary.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the client and cleans up any underlying resources, like HTTP sessions."""
        ...
