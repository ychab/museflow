from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class PageResponse[T](BaseModel):
    """One page of a collection, paged by offset."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int = Field(description="How many items the whole collection holds, all pages together")
    limit: int
    offset: int


class SuccessResponse(BaseModel):
    message: str
