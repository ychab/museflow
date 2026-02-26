import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class OAuthProviderState:
    """User state send to library provider in order to get its oauth token."""

    id: int

    user_id: uuid.UUID
    provider: MusicProvider
    state: str

    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class OAuthProviderUserToken:
    """User persistent auth token provider"""

    id: int
    user_id: uuid.UUID
    provider: MusicProvider

    token_type: str
    token_access: str
    token_refresh: str
    token_expires_at: datetime

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return datetime.now(UTC) >= self.token_expires_at - timedelta(seconds=buffer_seconds)
