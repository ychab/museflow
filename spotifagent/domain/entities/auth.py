import uuid

from pydantic import AwareDatetime
from pydantic import Field

from spotifagent.domain.entities.base import BaseEntity
from spotifagent.domain.entities.music import MusicProvider


class OAuthProviderState(BaseEntity):
    id: int

    user_id: uuid.UUID
    provider: MusicProvider
    state: str = Field(max_length=512)

    created_at: AwareDatetime
    updated_at: AwareDatetime
