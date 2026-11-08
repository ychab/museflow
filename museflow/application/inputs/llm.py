import uuid
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel
from pydantic import Field

from museflow.domain.enums import LLMOperation


class LLMUsageEntryInput(BaseModel):
    """One exported LLM usage row.

    The profile travels by name, as its id changes across databases; the playlist link is dropped, as playlists are not
    exported.
    """

    run_id: uuid.UUID
    operation: LLMOperation
    profile_name: str | None = None
    step: str
    model: str
    calls: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    cost: Decimal = Field(ge=0)
    duration: timedelta
    created_at: datetime
