"""The schemas every version of the API shares: its errors, its paging parameters, its health check."""

from typing import Any

from pydantic import BaseModel


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


class HealthCheckResponse(BaseModel):
    status: str
    database: str
