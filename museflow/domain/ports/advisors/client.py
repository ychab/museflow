from abc import ABC
from abc import abstractmethod
from typing import Any

from pydantic import HttpUrl

from museflow.domain.entities.music import SuggestedTrack


class AdvisorClientPort(ABC):
    @property
    @abstractmethod
    def base_url(self) -> HttpUrl: ...

    @abstractmethod
    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[SuggestedTrack]: ...

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
