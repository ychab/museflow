import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class OAuthProviderState:
    """Represents the state sent to an OAuth music provider during the authorization flow.

    This state is used to maintain context between the authorization request and the callback,
    ensuring security and associating the response with the correct user and provider.
    """

    id: int

    user_id: uuid.UUID
    provider: MusicProvider
    state: str

    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class OAuthProviderUserToken:
    """Represents a user's persistent OAuth token for a specific music provider.

    This entity stores the necessary tokens (access and refresh) and their expiration
    information, allowing the application to interact with the music provider on behalf
    of the user.
    """

    id: int
    user_id: uuid.UUID
    provider: MusicProvider

    token_type: str
    token_access: str
    token_refresh: str
    token_expires_at: datetime

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Checks if the access token is expired, considering a buffer period.

        Args:
            buffer_seconds: An integer representing a buffer in seconds. The token
                            will be considered expired if its expiration time is
                            within this buffer from the current time. This helps
                            to refresh tokens proactively before they actually expire.

        Returns:
            True if the token is expired or will expire within the buffer, False otherwise.
        """
        return datetime.now(UTC) >= self.token_expires_at - timedelta(seconds=buffer_seconds)
