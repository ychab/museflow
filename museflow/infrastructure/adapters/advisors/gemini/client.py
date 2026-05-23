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

from museflow.application.ports.advisors.agent import AdvisorAgentPort
from museflow.application.ports.advisors.similar import AdvisorSimilarPort
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import AdvisorRateLimitExceeded
from museflow.domain.exceptions import DiscoveryTasteStrategyException
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.domain.types import DiscoveryFocus
from museflow.domain.utils import taste as taste_utils
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.advisors.gemini.mappers import to_discovery_strategy
from museflow.infrastructure.adapters.advisors.gemini.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.gemini.schemas import GEMINI_DISCOVERY_STRATEGY_CONFIG
from museflow.infrastructure.adapters.advisors.gemini.schemas import GEMINI_TRACK_SUGGESTIONS_CONFIG
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiDiscoveryStrategyContent
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTracksContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.common.gemini.utils import parse_retry_delay
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


class GeminiAdvisorAdapter(HttpClientMixin, AdvisorSimilarPort, AdvisorAgentPort):
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
                retry_delay = parse_retry_delay(e.response.content)
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
                                f'Suggest {limit} tracks similar to "{track_name}" by "{artist_name}" '
                                f"based on genre, mood, and musical style. "
                                f"Return diverse suggestions from different artists. "
                                f"Do not include the seed track itself. "
                                f"For each track, assign a similarity score between 0.0 and 1.0 "
                                f"where 1.0 means nearly identical style."
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

    async def get_discovery_strategy(
        self,
        profile: TasteProfile,
        focus: DiscoveryFocus,
        similar_limit: int,
        genre: str | None = None,
        mood: str | None = None,
        custom_instructions: str | None = None,
        excluded_tracks: list[TrackSuggested] | None = None,
    ) -> DiscoveryTasteStrategy:
        data = profile.profile

        timeline_summary = taste_utils.timeline_summary(data)
        core_identity_str = taste_utils.core_identity_summary(data)
        behavioral_traits_str = taste_utils.behavioral_traits_summary(data)
        archetype = taste_utils.personality_archetype(data)
        oldest_era = taste_utils.oldest_era_label(data)
        current_era = taste_utils.current_era_label(data)

        focus_descriptions = {
            DiscoveryFocus.EXPANSION: "Find high-probability cousin genres not yet explored.",
            DiscoveryFocus.ROOTS_REVIVAL: f"Find modern tracks replicating the technical fingerprint of the oldest era ({oldest_era}).",
            DiscoveryFocus.CULTURAL_BRIDGE: f"Find music at the intersection of {oldest_era} and {current_era}.",
        }

        exclusion_block = ""
        if excluded_tracks:
            formatted = "\n".join(f"- {t.artists[0]}: {t.name}" for t in excluded_tracks)
            exclusion_block = (
                "### EXCLUSION LIST (DO NOT SUGGEST THESE)\n"
                "These tracks have already been considered in this session. "
                "You MUST suggest DIFFERENT tracks and avoid these artists where possible:\n"
                f"{formatted}\n\n"
            )

        system_prompt = (
            "### ROLE\n"
            'You are the "MuseFlow Navigator," a world-class musicologist.\n'
            "Your goal: recommend NEW music the user has never heard, based on their Taste Profile.\n\n"
            f"### USER IDENTITY: {archetype}\n"
            f"- Core Identity: {core_identity_str}\n"
            f"- Behavioral Traits: {behavioral_traits_str}\n"
            f"- Taste Timeline (oldest → newest): {timeline_summary}\n\n"
            f"{exclusion_block}"
            "### FOCUS STRATEGIES\n"
            f"- expansion: {focus_descriptions[DiscoveryFocus.EXPANSION]}\n"
            f"- roots_revival: {focus_descriptions[DiscoveryFocus.ROOTS_REVIVAL]}\n"
            f"- cultural_bridge: {focus_descriptions[DiscoveryFocus.CULTURAL_BRIDGE]}\n\n"
            "### CONSTRAINTS\n"
            "- Return ONLY the JSON object (schema enforced).\n"
            "- recommended_tracks MUST be tracks the user has NOT heard before — they are new discoveries.\n"
            "- recommended_tracks MUST NOT appear in the Exclusion List above.\n"
            "- If exclusions are provided, pivot to deeper cuts or adjacent artists to ensure variety.\n"
            f"- Provide {similar_limit} recommended tracks, each with a discovery score (0.0–1.0, higher = better fit).\n"
            "- Provide 2-3 specific search_queries to widen the discovery surface.\n"
            "- Keep suggested_playlist_name creative and thematic.\n"
        )

        user_parts = [f"Apply the '{focus.value}' focus strategy."]
        if genre:
            user_parts.append(f"Preferred genre: {genre}.")
        if mood:
            user_parts.append(f"Desired mood: {mood}.")
        if custom_instructions:
            user_parts.append(f"Additional instructions: {custom_instructions}")
        user_message = " ".join(user_parts)

        request = GeminiGenerateContentRequest(
            system_instruction=GeminiRequestContent(parts=[GeminiRequestPart(text=system_prompt)]),
            contents=[GeminiRequestContent(parts=[GeminiRequestPart(text=user_message)])],
            generationConfig=GEMINI_DISCOVERY_STRATEGY_CONFIG,
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
                "Gemini rate limit exceeded after max retries for discovery strategy"
            ) from e

        envelope = GeminiResponse.model_validate(response_data)

        if not envelope.candidates:
            raise DiscoveryTasteStrategyException("Gemini returned no candidates for discovery strategy")

        raw_text = envelope.candidates[0].content.parts[0].text
        try:
            inner = GeminiDiscoveryStrategyContent.model_validate(json.loads(raw_text))
        except (ValidationError, ValueError) as e:
            raise DiscoveryTasteStrategyException("Invalid Gemini response for discovery strategy") from e

        return to_discovery_strategy(inner)
