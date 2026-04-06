import asyncio
import json
import logging
from typing import Any
from typing import cast

import httpx
from httpx import codes

from pydantic import HttpUrl
from pydantic import ValidationError

from tenacity import TryAgain
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.exceptions import ProfilerRateLimitExceeded
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.common.gemini.utils import parse_retry_delay
from museflow.infrastructure.adapters.http import HttpClientMixin
from museflow.infrastructure.adapters.profilers.gemini.schemas import GEMINI_TASTE_PROFILE_CONFIG
from museflow.infrastructure.adapters.profilers.gemini.schemas import GeminiTasteProfileContent
from museflow.infrastructure.config.settings.gemini import gemini_settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, ProfilerRateLimitExceeded):
        return False  # Rate limit exhausted — let it propagate

    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    # Retry network error OR manual retry signal (used for 429 with retryDelay)
    if isinstance(exception, (httpx.RequestError, TryAgain)):
        return True

    return False


def _format_tracks(tracks: list[Track]) -> str:
    lines = []

    for track in tracks:
        date_parts = []
        if track.added_at:
            date_parts.append(f"added:{track.added_at.date()}")
        if track.played_at:
            date_parts.append(f"last_played:{track.played_at.date()}")
        date_label = ", ".join(date_parts) if date_parts else "no_date"

        artists = " & ".join(artist.name for artist in track.artists)
        genres = ", ".join(track.genres) if track.genres else "unknown"

        lines.append(f"{date_label} | {artists} - {track.name} | genres: {genres}")

    return "\n".join(lines)


class GeminiTasteProfileAdapter(HttpClientMixin, TasteProfilerPort):
    def __init__(
        self,
        api_key: str,
        segment_model: GeminiModel,
        merge_model: GeminiModel,
        reflect_model: GeminiModel,
        base_url: HttpUrl | None = None,
        timeout: float = 120.0,
        verify_ssl: bool = True,
        max_retry_wait: int = 60,
    ) -> None:
        super().__init__(
            base_url=base_url or gemini_settings.BASE_URL,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._api_key = api_key
        self._segment_model = segment_model
        self._merge_model = merge_model
        self._reflect_model = reflect_model
        self._max_retry_wait = max_retry_wait

    @property
    def display_name(self) -> str:
        return "Gemini"

    @property
    def profiler_type(self) -> TasteProfiler:
        return TasteProfiler.GEMINI

    @property
    def logic_version(self) -> str:
        return "v1.0"

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
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
                            "Gemini profiler rate limit wait exceeds max, aborting",
                            extra={"retry_delay": retry_delay, "max_retry_wait": self._max_retry_wait},
                        )
                        raise ProfilerRateLimitExceeded(
                            f"Gemini rate limit {retry_delay}s exceeds max wait {self._max_retry_wait}s"
                        ) from e

                    logger.debug(f"Gemini profiler rate limit exceeded, retrying in {retry_delay} seconds")
                    await asyncio.sleep(retry_delay + 1)
                    raise TryAgain() from e

            logger.exception(
                "Gemini profiler API error",
                extra={"status_code": e.response.status_code, "method": method, "endpoint": endpoint},
            )
            raise e

        if response.status_code == codes.NO_CONTENT:
            return {}

        return response.json()

    async def _prompt_request(self, prompt: str, model: GeminiModel) -> TasteProfileData:
        request = GeminiGenerateContentRequest(
            contents=[GeminiRequestContent(parts=[GeminiRequestPart(text=prompt)])],
            generationConfig=GEMINI_TASTE_PROFILE_CONFIG,
        )

        try:
            response_data = await self.make_api_call(
                method="POST",
                endpoint=f"/models/{model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json_data=request.model_dump(exclude_none=True),
            )
        except TryAgain as e:
            raise ProfilerRateLimitExceeded("Gemini profiler rate limit exceeded after max retries") from e

        envelope = GeminiResponse.model_validate(response_data)
        raw_text = envelope.candidates[0].content.parts[0].text

        try:
            content = GeminiTasteProfileContent.model_validate(json.loads(raw_text))
        except (ValidationError, ValueError) as e:
            raise TasteProfileBuildException(f"Invalid Gemini taste profile response: {e}") from e

        return cast(TasteProfileData, content.model_dump())

    async def build_profile_segment(self, tracks: list[Track]) -> TasteProfileData:
        dates = [t.played_at or t.added_at for t in tracks if t.played_at or t.added_at]
        if dates:
            min_date = min(d for d in dates if d is not None).date()
            max_date = max(d for d in dates if d is not None).date()
            date_range = f"{min_date} to {max_date}"
        else:
            date_range = "unknown period"

        prompt = (
            f"Analyze these {len(tracks)} tracks from [{date_range}]. Build a musical taste profile segment.\n"
            "Return JSON with exactly these keys:\n"
            '- "taste_timeline": one TasteEra for this batch\n'
            '- "core_identity": {genre_or_mood: weight 0-1} long-term affinity signals\n'
            '- "current_vibe": {genre_or_mood: weight 0-1} what this batch reveals right now\n'
            '- "personality_archetype": null\n'
            '- "life_phase_insights": []\n'
            "\nTracks:\n"
            f"{_format_tracks(tracks)}"
        )
        return await self._prompt_request(prompt, self._segment_model)

    async def merge_profiles(self, foundation: TasteProfileData, new_segment: TasteProfileData) -> TasteProfileData:
        foundation_json = json.dumps(foundation, ensure_ascii=False)
        segment_json = json.dumps(new_segment, ensure_ascii=False)

        prompt = (
            "You are evolving a Master Taste Profile with new listening data.\n\n"
            f"Existing profile:\n{foundation_json}\n\n"
            f"New segment:\n{segment_json}\n\n"
            "Rules:\n"
            "- taste_timeline: decide if this segment continues the last era or starts a new one. "
            "Append or extend. Do not let it grow indefinitely — merge consecutive eras if very similar.\n"
            "- core_identity: weighted blend, foundation heavier (long-term DNA, do not erase)\n"
            "- current_vibe: new segment heavier (reflects recent pivots)\n"
            "- personality_archetype: keep null (set by final pass)\n"
            "- life_phase_insights: keep empty (set by final pass)\n\n"
            "Return the same JSON structure."
        )

        return await self._prompt_request(prompt, self._merge_model)

    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        profile_json = json.dumps(profile, ensure_ascii=False)

        prompt = (
            "You have the complete Master Taste Profile of a listener across their entire library.\n\n"
            f"Profile:\n{profile_json}\n\n"
            "Perform a final psychographic reflection. Populate:\n"
            '- "personality_archetype": one evocative label (e.g. "The Architect of Sound")\n'
            '- "life_phase_insights": list of observed life transitions\n'
            '  (e.g. "Shift from high-energy industrial to calming ambient during 2024")\n\n'
            "Return the full profile JSON with these two fields populated. Keep all other fields unchanged."
        )

        return await self._prompt_request(prompt, self._reflect_model)
