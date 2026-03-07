from abc import ABC
from abc import abstractmethod
from typing import Any

from pydantic import HttpUrl

from museflow.domain.entities.music import TrackSuggested


class AdvisorClientPort(ABC):
    @property
    @abstractmethod
    def base_url(self) -> HttpUrl: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @abstractmethod
    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[TrackSuggested]: ...

    @abstractmethod
    async def make_api_call(
        self,
        method: str,
        endpoint: str | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def close(self) -> None: ...
