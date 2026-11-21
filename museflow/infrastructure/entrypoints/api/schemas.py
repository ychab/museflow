import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field

from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType


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


class PageParams(BaseModel):
    limit: int
    offset: int


class PageResponse[T](BaseModel):
    """One page of a collection, paged by offset."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int = Field(description="How many items the whole collection holds, all pages together")
    limit: int
    offset: int


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


class PlaylistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: PlaylistType
    provider: MusicProvider
    provider_id: str
    prompt: str | None
    focus: DiscoveryFocus | None
    created_at: datetime
