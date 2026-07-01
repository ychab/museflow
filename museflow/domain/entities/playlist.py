import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime

from museflow.domain.entities.base import BaseProviderEntity
from museflow.domain.entities.track import Track
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import PlaylistType


@dataclass(frozen=True, kw_only=True)
class Playlist(BaseProviderEntity):
    type: PlaylistType
    snapshot_id: str | None = None
    tracks: list[Track] = field(default_factory=list)

    # Discovery-specific — nullable, populated by the use case that creates a PlaylistType.DISCOVERY playlist.
    profile_id: uuid.UUID | None = None
    reasoning: str | None = None
    focus: DiscoveryFocus | None = None
    genre: str | None = None
    mood: str | None = None
    custom_instructions: str | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
