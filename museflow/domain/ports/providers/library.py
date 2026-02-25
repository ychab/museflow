from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track


class ProviderLibraryPort(ABC):
    @abstractmethod
    async def get_top_artists(self, page_limit: int, time_range: str | None = None) -> list[Artist]: ...

    @abstractmethod
    async def get_top_tracks(self, page_limit: int, time_range: str | None = None) -> list[Track]: ...

    @abstractmethod
    async def get_saved_tracks(self, page_limit: int) -> list[Track]: ...

    @abstractmethod
    async def get_playlist_tracks(self, page_limit: int) -> list[Track]: ...
