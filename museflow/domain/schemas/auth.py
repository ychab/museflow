from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from museflow.domain.schemas.base import BaseEntity


class OAuthProviderTokenPayload(BaseEntity):
    """
    Represents the raw, transient OAuth2 token data exchanged with an external provider.

    This schema acts as a Value Object within the Domain Layer, primarily used by
    Ports (ProviderClientPort) to define the structure of authentication credentials
    received from or sent to third-party services.

    Unlike the `OAuthProviderUserToken` Entity, this object has no identity or persistence;
    it is purely a data container for access tokens, refresh tokens, and expiry information.
    """

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: AwareDatetime


class OAuthProviderUserTokenCreate(BaseEntity):
    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime


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
