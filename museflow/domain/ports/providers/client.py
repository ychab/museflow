from abc import ABC
from abc import abstractmethod
from typing import Any

from pydantic import HttpUrl

from museflow.domain.entities.auth import OAuthProviderTokenState


class ProviderOAuthClientPort(ABC):
    """Port interface for OAuth stateless provider API client."""

    @property
    @abstractmethod
    def base_url(self) -> HttpUrl: ...

    @property
    @abstractmethod
    def token_endpoint(self) -> HttpUrl: ...

    @abstractmethod
    def get_authorization_url(self, state: str) -> HttpUrl:
        """Generate OAuth authorization URL."""
        ...

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> OAuthProviderTokenState:
        """Exchange authorization code for access token."""
        ...

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> OAuthProviderTokenState:
        """Refresh an expired access token."""
        ...

    @abstractmethod
    async def make_user_api_call(
        self,
        method: str,
        endpoint: str,
        token_state: OAuthProviderTokenState,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated user API call."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the client and cleanup resources."""
        ...
