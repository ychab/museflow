import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class BaseProviderEntity(ABC):
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    name: str

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str
