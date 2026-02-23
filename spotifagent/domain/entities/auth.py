import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from pydantic import AwareDatetime
from pydantic import Field

from spotifagent.domain.entities.base import BaseEntity
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.spotify import SpotifyAccountCreate
from spotifagent.domain.entities.spotify import SpotifyAccountUpdate


class OAuthProviderState(BaseEntity):
    id: int

    user_id: uuid.UUID
    provider: MusicProvider
    state: str = Field(max_length=512)

    created_at: AwareDatetime
    updated_at: AwareDatetime


class OAuthProviderTokenState(BaseEntity):
    """User token state with expiration tracking."""

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: AwareDatetime

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return datetime.now(UTC) >= self.expires_at - timedelta(seconds=buffer_seconds)

    def to_user_create(self) -> SpotifyAccountCreate:
        return SpotifyAccountCreate(
            token_type=self.token_type,
            token_access=self.access_token,
            token_refresh=self.refresh_token,
            token_expires_at=self.expires_at,
        )

    def to_user_update(self) -> SpotifyAccountUpdate:
        return SpotifyAccountUpdate(
            token_type=self.token_type,
            token_access=self.access_token,
            token_refresh=self.refresh_token,
            token_expires_at=self.expires_at,
        )
