import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text


@dataclass(frozen=True, kw_only=True)
class BlacklistedArtist:
    id: uuid.UUID
    user_id: uuid.UUID

    artist_name: str
    fingerprint: str = ""

    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.artist_name:
            raise ValueError("artist_name must not be empty")
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", normalize_text(self.artist_name))


@dataclass(frozen=True, kw_only=True)
class BlacklistedTrack:
    id: uuid.UUID
    user_id: uuid.UUID

    name: str
    artist_name: str
    fingerprint: str = ""

    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.artist_name:
            raise ValueError("artist_name must not be empty")
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", generate_fingerprint(self.name, [self.artist_name]))
