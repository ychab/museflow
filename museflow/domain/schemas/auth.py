from typing import Self

from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from museflow.domain.schemas.base import BaseEntity


class OAuthProviderTokenState(BaseEntity):
    """User non-persistent token state."""

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: AwareDatetime


class OAuthProviderUserTokenCreate(BaseEntity):
    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime

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
