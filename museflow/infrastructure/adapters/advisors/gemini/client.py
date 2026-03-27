import json
import logging

from pydantic import HttpUrl
from pydantic import ValidationError

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.domain.entities.music import TrackSuggested
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
    ) -> None:
        super().__init__(
            base_url=base_url or gemini_settings.BASE_URL,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._api_key = api_key
        self._model = model

    @property
    def display_name(self) -> str:
        return "Gemini"

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

        response_data = await self.make_api_call(
            method="POST",
            endpoint=f"/models/{self._model}:generateContent",
            headers={"x-goog-api-key": self._api_key},
            json_data=request.model_dump(exclude_none=True),
        )

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
