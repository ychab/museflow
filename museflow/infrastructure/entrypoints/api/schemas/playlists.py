import uuid
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict

from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType


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
