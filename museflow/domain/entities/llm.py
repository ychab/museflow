import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime

from museflow.domain.enums import LLMOperation
from museflow.domain.value_objects.llm import LLMUsage


@dataclass(frozen=True, kw_only=True)
class LLMUsageRecord:
    """What one command run spent on one step and model."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    run_id: uuid.UUID
    operation: LLMOperation
    usage: LLMUsage

    # Null when the command had none (enrich, dry-run) or once the profile or playlist is deleted.
    profile_id: uuid.UUID | None = None
    playlist_id: uuid.UUID | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
