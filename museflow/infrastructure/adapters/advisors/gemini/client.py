import asyncio
import json
import logging
from typing import Any

import httpx
from httpx import codes

from pydantic import HttpUrl
from pydantic import ValidationError

from tenacity import TryAgain
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.exceptions import AdvisorRateLimitExceeded
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.infrastructure.adapters.advisors.gemini.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.gemini.schemas import GEMINI_TRACK_SUGGESTIONS_CONFIG
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTracksContent
from museflow.infrastructure.adapters.advisors.gemini.types import GeminiModel
from museflow.infrastructure.adapters.http import HttpClientMixin
from museflow.infrastructure.config.settings.gemini import gemini_settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, AdvisorRateLimitExceeded):
        return False  # Rate limit exhausted — let it propagate

    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    # Retry network error OR manual retry signal (used for 429 with retryDelay)
    if isinstance(exception, (httpx.RequestError, TryAgain)):
        return True

    return False


class GeminiClientAdapter(HttpClientMixin, AdvisorClientPort):
    """Adapter for the Google Gemini API.

    This class implements the `AdvisorClientPort` and provides methods to interact
    with the Gemini generative language API to get similar track suggestions. It
    includes retry logic for transient network errors and specific HTTP status codes
    via `HttpClientMixin`.
    """

    def __init__(
        self,
        api_key: str,
        model: GeminiModel,
        base_url: HttpUrl | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        max_retry_wait: int = 60,
    ) -> None:
        super().__init__(
            base_url=base_url or gemini_settings.BASE_URL,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._api_key = api_key
        self._model = model
        self._max_retry_wait = max_retry_wait

    @property
    def display_name(self) -> str:
        return "Gemini"

    @staticmethod
    def _parse_retry_delay(content: bytes) -> int | None:
        """Extracts the retryDelay (in seconds) from a Gemini 429 response body.

        Gemini embeds the delay inside error.details[] under the RetryInfo entry,
        as a string like "38s". Returns None if the body is malformed or missing.
        """
        try:
            body = json.loads(content)
            for detail in body.get("error", {}).get("details", []):
                if detail.get("@type", "").endswith("RetryInfo") and "retryDelay" in detail:
                    return int(float(detail["retryDelay"].rstrip("s")))
        except (ValueError, KeyError, AttributeError, TypeError):
            pass
        return None

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),  # 2 + 4 + 8 + 16 + 32 = 62 seconds
        stop=stop_after_attempt(gemini_settings.HTTP_MAX_RETRIES),
        reraise=True,
    )
    async def make_api_call(
        self,
        method: str,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Makes an API call to the Gemini API.

        This method includes retry logic for transient errors and rate limiting.
        It specifically handles the `retryDelay` field from Gemini's 429 response body.
        """
        try:
            response = await self._client.request(
                method=method.upper(),
                url=f"{str(self._base_url).rstrip('/')}{endpoint}",
                headers=headers,
                params=params,
                json=json_data,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == codes.TOO_MANY_REQUESTS:
                retry_delay = self._parse_retry_delay(e.response.content)
                if retry_delay is not None:
                    if retry_delay > self._max_retry_wait:
                        logger.warning(
                            "Gemini rate limit wait exceeds max, aborting",
                            extra={"retry_delay": retry_delay, "max_retry_wait": self._max_retry_wait},
                        )
                        raise AdvisorRateLimitExceeded(
                            f"Gemini rate limit {retry_delay}s exceeds max wait {self._max_retry_wait}s"
                        ) from e

                    logger.debug(f"Gemini rate limit exceeded, retrying in {retry_delay} seconds")
                    await asyncio.sleep(retry_delay + 1)
                    raise TryAgain() from e

            logger.exception(
                "Gemini API Error",
                extra={"status_code": e.response.status_code, "method": method, "endpoint": endpoint},
            )
            raise e

        if response.status_code == codes.NO_CONTENT:
            return {}

        return response.json()

    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[TrackSuggested]:
        request = GeminiGenerateContentRequest(
            contents=[
                GeminiRequestContent(
                    parts=[
                        GeminiRequestPart(
                            text=(
                                f"You are a music recommendation engine. "
                                f'Suggest {limit} tracks similar to "{track_name}" by "{artist_name}".'
                            )
                        )
                    ]
                )
            ],
            generationConfig=GEMINI_TRACK_SUGGESTIONS_CONFIG,
        )

        try:
            response_data = await self.make_api_call(
                method="POST",
                endpoint=f"/models/{self._model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json_data=request.model_dump(exclude_none=True),
            )
        except TryAgain as e:
            raise AdvisorRateLimitExceeded(
                f"Gemini rate limit exceeded after max retries for '{track_name}' by '{artist_name}'"
            ) from e

        envelope = GeminiResponse.model_validate(response_data)

        if not envelope.candidates:
            return []

        raw_text = envelope.candidates[0].content.parts[0].text
        try:
            inner = GeminiSuggestedTracksContent.model_validate(json.loads(raw_text))
        except (ValidationError, ValueError) as e:
            raise SimilarTrackResponseException(
                f"Invalid Gemini response for artist: {artist_name} and track: {track_name}",
            ) from e

        return [to_track_suggested(track) for track in inner.tracks]
