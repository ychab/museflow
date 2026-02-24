import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Self

from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from spotifagent.domain.entities.base import BaseEntity
from spotifagent.domain.entities.music import MusicProvider


class OAuthProviderState(BaseEntity):
    """User state send to music provider in order to get its oauth token."""

    id: int

    user_id: uuid.UUID
    provider: MusicProvider
    state: str = Field(max_length=512)

    created_at: AwareDatetime
    updated_at: AwareDatetime


class OAuthProviderTokenState(BaseEntity):
    """User "volatile" token state with expiration tracking."""

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: AwareDatetime

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return datetime.now(UTC) >= self.expires_at - timedelta(seconds=buffer_seconds)


class BaseOAuthProviderUserToken(BaseEntity):
    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime


class OAuthProviderUserToken(BaseOAuthProviderUserToken):
    """User persistent auth token provider"""

    id: int
    user_id: uuid.UUID
    provider: MusicProvider

    def refresh_from_token_state(self, token_state: OAuthProviderTokenState) -> None:
        self.token_type = token_state.token_type
        self.token_access = token_state.access_token
        self.token_refresh = token_state.refresh_token
        self.token_expires_at = token_state.expires_at

    def to_token_state(self) -> OAuthProviderTokenState:
        return OAuthProviderTokenState(
            token_type=self.token_type,
            access_token=self.token_access,
            refresh_token=self.token_refresh,
            expires_at=self.token_expires_at,
        )


class OAuthProviderUserTokenCreate(BaseOAuthProviderUserToken):
    @classmethod
    def from_token_state(cls, token_state: OAuthProviderTokenState) -> Self:
        return cls(
            token_type=token_state.token_type,
            token_access=token_state.access_token,
            token_refresh=token_state.refresh_token,
            token_expires_at=token_state.expires_at,
        )


class OAuthProviderUserTokenUpdate(BaseEntity):
    token_type: str | None = Field(None, max_length=512)
    token_access: str | None = Field(None, max_length=512)
    token_refresh: str | None = Field(None, max_length=512)
    token_expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_one_field_set(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self

    @classmethod
    def from_token_state(cls, token_state: OAuthProviderTokenState) -> Self:
        return cls(
            token_type=token_state.token_type,
            token_access=token_state.access_token,
            token_refresh=token_state.refresh_token,
            token_expires_at=token_state.expires_at,
        )
