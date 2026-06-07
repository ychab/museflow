import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from museflow.domain.entities.music import Track
from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class DiscoveryPlaylist:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    profile_id: uuid.UUID

    provider: MusicProvider
    provider_id: str

    tracks: list[Track] = field(default_factory=list)

    name: str
    reasoning: str
    focus: DiscoveryFocus
    genre: str | None
    mood: str | None
    custom_instructions: str | None

    created_at: datetime
    updated_at: datetime
