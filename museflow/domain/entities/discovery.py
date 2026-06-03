import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicProvider
from museflow.domain.utils.text import generate_fingerprint


@dataclass(frozen=True, kw_only=True)
class DiscoveryPlaylistTrack:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    playlist_id: uuid.UUID

    provider: MusicProvider
    provider_id: str

    track_name: str
    artist_names: list[str]
    position: int

    fingerprint: str = ""
    score: int | None = None

    def __post_init__(self) -> None:
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", generate_fingerprint(self.track_name, [self.artist_names[0]]))


@dataclass(frozen=True, kw_only=True)
class DiscoveryPlaylist:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    profile_id: uuid.UUID

    provider: MusicProvider
    provider_id: str

    tracks: list[DiscoveryPlaylistTrack] = field(default_factory=list)

    name: str
    reasoning: str
    focus: DiscoveryFocus
    genre: str | None
    mood: str | None
    custom_instructions: str | None

    created_at: datetime
    updated_at: datetime
