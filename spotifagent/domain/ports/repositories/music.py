import uuid
from abc import ABC
from abc import abstractmethod

from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack


class TopArtistRepositoryPort(ABC):
    @abstractmethod
    async def bulk_upsert(self, top_artists: list[TopArtist], batch_size: int) -> tuple[list[uuid.UUID], int]: ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID) -> int: ...


class TopTrackRepositoryPort(ABC):
    @abstractmethod
    async def bulk_upsert(self, top_tracks: list[TopTrack], batch_size: int) -> tuple[list[uuid.UUID], int]: ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID) -> int: ...
