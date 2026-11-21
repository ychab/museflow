import uuid
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr


class HealthCheckResponse(BaseModel):
    status: str
    database: str


class ProblemDetails(BaseModel):
    """An error body, as RFC 9457 describes it."""

    # No URI per problem yet: `about:blank` says the title is the HTTP status phrase
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    # The fields that failed validation (422 only): each holds the input it got, of any JSON type
    errors: list[dict[str, Any]] | None = None


class SuccessResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool


class UserWithToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    access_token: str
    token_type: str = "Bearer"


class ProviderConnectResponse(BaseModel):
    authorization_url: str


class ProviderConnectCompleteRequest(BaseModel):
    # What the provider appended to the redirect URI, which the client reads back
    code: str
    state: str
