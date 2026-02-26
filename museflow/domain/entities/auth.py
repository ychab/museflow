import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Self

from museflow.domain.schemas.auth import OAuthProviderTokenState
from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class OAuthProviderState:
    """User state send to music provider in order to get its oauth token."""

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

    @classmethod
    def from_token_state(
        cls,
        auth_token_id: int,
        user_id: uuid.UUID,
        provider: MusicProvider,
        token_state: OAuthProviderTokenState,
    ) -> Self:
        return cls(
            id=auth_token_id,
            user_id=user_id,
            provider=provider,
            token_type=token_state.token_type,
            token_access=token_state.access_token,
            token_refresh=token_state.refresh_token,
            token_expires_at=token_state.expires_at,
        )

    def to_token_state(self) -> OAuthProviderTokenState:
        return OAuthProviderTokenState(
            token_type=self.token_type,
            access_token=self.token_access,
            refresh_token=self.token_refresh,
            expires_at=self.token_expires_at,
        )
