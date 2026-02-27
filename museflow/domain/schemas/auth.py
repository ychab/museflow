from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from museflow.domain.schemas.base import BaseEntity


class OAuthProviderTokenPayload(BaseEntity):
    """Represents the raw, transient OAuth2 token data from an external provider.

    This schema is a Value Object used by provider clients to structure authentication
    credentials. It is not persisted and has no identity, serving purely as a data
    container for tokens and expiry information.
    """

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: AwareDatetime


class OAuthProviderUserTokenCreate(BaseEntity):
    """Schema for creating a new `OAuthProviderUserToken` entity.

    Defines the required fields for creating a persistent record of a user's OAuth
    token for a music provider.
    """

    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime


class OAuthProviderUserTokenUpdate(BaseEntity):
    """Schema for updating an existing `OAuthProviderUserToken` entity.

    Allows for partial updates of a user's OAuth token, such as refreshing the
    access token or extending its expiration.
    """

    token_type: str | None = Field(None, max_length=512)
    token_access: str | None = Field(None, max_length=512)
    token_refresh: str | None = Field(None, max_length=512)
    token_expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_one_field_set(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self
