import logging
from typing import Any

import httpx
from httpx import codes

from pydantic import HttpUrl

from tenacity import retry
from tenacity import retry_if_exception
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from museflow.domain.entities.music import TrackSuggested
from museflow.domain.ports.advisors.client import AdvisorClientPort
from museflow.infrastructure.adapters.advisors.lastfm.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmSimilarTracksResponse
from museflow.infrastructure.config.settings.lastfm import lastfm_settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.RequestError):  # Retry network error
        return True

    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    return False


class LastFmClientAdapter(AdvisorClientPort):
    def __init__(
        self,
        client_api_key: str,
        client_secret: str,
        base_url: HttpUrl | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.client_api_key = client_api_key
        self.client_secret = client_secret

        self._base_url = base_url or HttpUrl("http://ws.audioscrobbler.com/2.0/")

        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def base_url(self) -> HttpUrl:
        return self._base_url

    @property
    def display_name(self) -> str:
        return "Last.fm"

    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[TrackSuggested]:
        tracks_suggested: list[TrackSuggested] = []

        response_data = await self.make_api_call(
            method="GET",
            params={
                "method": "track.getSimilar",
                "artist": artist_name,
                "track": track_name,
                "limit": limit,
                "autocorrect": 1,
            },
        )

        page = LastFmSimilarTracksResponse.model_validate(response_data)
        if page.error or page.message:
            logger.debug(
                f"Error occurred while fetching similar tracks for artist:'{artist_name}' and track:'{track_name}' "
                f"with error: {page.error or 0} and message: {page.message or ''}"
            )

        if page.similartracks:
            tracks_suggested = [to_track_suggested(track) for track in page.similartracks.track]

        return tracks_suggested

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),  # 2 + 4 + 8 + 16 + 32 = 62 seconds
        stop=stop_after_attempt(lastfm_settings.HTTP_MAX_RETRIES),
        reraise=True,
    )
    async def make_api_call(
        self,
        method: str,
        endpoint: str | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.request(
            method=method.upper(),
            url=f"{self.base_url}",
            params={
                "api_key": self.client_api_key,
                "format": "json",
                **(params or {}),
            },
        )
        response.raise_for_status()

        if response.status_code == codes.NO_CONTENT:
            return {}

        return response.json()

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "LastFmClientAdapter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
