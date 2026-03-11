from pydantic import AwareDatetime
from pydantic import Field
from pydantic import model_validator

from museflow.application.inputs.base import BaseInput


class OAuthProviderUserTokenCreateInput(BaseInput):
    """Schema for creating a new `OAuthProviderUserTokenCreateInput` entity.

    Defines the required fields for creating a persistent record of a user's OAuth
    token for a music provider.
    """

    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime


class OAuthProviderUserTokenUpdateInput(BaseInput):
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
