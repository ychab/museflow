import json
import logging

from pydantic import HttpUrl
from pydantic import ValidationError

from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.domain.entities.track import Track
from museflow.domain.types import GENRE_MACRO_TAGS
from museflow.domain.types import GENRE_MESO_TAGS
from museflow.domain.types import GENRE_MICRO_TAGS
from museflow.domain.types import GenreTag
from museflow.domain.types import MoodTag
from museflow.domain.value_objects.track import TrackEnrichment
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.enrichers.gemini.schemas import GEMINI_ENRICHMENT_CONFIG
from museflow.infrastructure.adapters.enrichers.gemini.schemas import GeminiEnrichmentResponse
from museflow.infrastructure.adapters.http import HttpClientMixin
from museflow.infrastructure.config.settings.gemini import gemini_settings

logger = logging.getLogger(__name__)


class GeminiTrackEnricherAdapter(HttpClientMixin, TrackEnricherPort):
    """Adapter that uses the Gemini API to infer genre and mood metadata for tracks."""

    def __init__(
        self,
        api_key: str,
        model: GeminiModel,
        base_url: HttpUrl | None = None,
        timeout: float = 180.0,
        verify_ssl: bool = True,
    ) -> None:
        super().__init__(
            base_url=base_url or gemini_settings.BASE_URL,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._api_key = api_key
        self._model = model

    async def enrich_tracks(self, tracks: list[Track]) -> list[TrackEnrichment]:
        request = GeminiGenerateContentRequest(
            system_instruction=GeminiRequestContent(
                parts=[
                    GeminiRequestPart(
                        text=(
                            "### ROLE\n"
                            "You are a music metadata expert. For each provided track, classify its genre(s) and mood(s).\n\n"
                            "### GENRE RULES\n"
                            "Return 2 to 3 genre tags per track, ordered from broadest to most specific.\n"
                            "Use ONLY values from the lists below — no synonyms, no paraphrases.\n\n"
                            f"genres[0] — macro (pick ONE): {', '.join(t.value for t in GENRE_MACRO_TAGS)}\n\n"
                            f"genres[1] — meso (pick ONE that fits the macro): {', '.join(t.value for t in GENRE_MESO_TAGS)}\n\n"
                            f"genres[2] — micro (pick ONE or omit if none applies): {', '.join(t.value for t in GENRE_MICRO_TAGS)}\n\n"
                            "Do NOT include artist names or track names as genres.\n\n"
                            "### MOOD RULES\n"
                            f"- Return 1 to 2 mood labels chosen ONLY from this exact vocabulary: {', '.join(m.value for m in MoodTag)}.\n"
                            "- Do NOT use any mood word outside this list.\n\n"
                            "### LOCALE RULE\n"
                            "- `locale`: Return the 2-letter ISO 639-1 code for the spoken language of the primary artist "
                            '(e.g. "fr", "en", "es", "pt", "ar", "ko").\n'
                            "- Infer from the primary artist's nationality/cultural context.\n"
                            "- If the track is instrumental or the language is genuinely ambiguous, omit the field.\n"
                            "- Do NOT guess. Only return a code you are confident about.\n\n"
                            "### OUTPUT\n"
                            "Return only the JSON object (schema enforced). "
                            "Use the track_index field to match each result back to the input track."
                        ),
                    ),
                ],
            ),
            contents=[
                GeminiRequestContent(
                    parts=[
                        GeminiRequestPart(
                            text=json.dumps(
                                [
                                    {"index": i, "title": track.name, "primary_artist": track.primary_artist}
                                    for i, track in enumerate(tracks)
                                ],
                                ensure_ascii=False,
                            ),
                        ),
                    ],
                ),
            ],
            generationConfig=GEMINI_ENRICHMENT_CONFIG,
        )

        response_data = await self.make_api_call(
            method="POST",
            endpoint=f"/models/{self._model}:generateContent",
            headers={"x-goog-api-key": self._api_key},
            json_data=request.model_dump(exclude_none=True),
        )

        envelope = GeminiResponse.model_validate(response_data)

        if not envelope.candidates:
            logger.warning("Gemini enricher returned no candidates")
            return []

        raw_text = envelope.candidates[0].content.parts[0].text
        try:
            content = GeminiEnrichmentResponse.model_validate(json.loads(raw_text))
        except (ValidationError, ValueError):
            logger.exception("Invalid Gemini enrichment response", extra={"raw": raw_text[:200]})
            return []

        return [
            TrackEnrichment(
                track_id=tracks[item.track_index].id,
                genres=[GenreTag(g) for g in item.genres if g in GenreTag._value2member_map_],
                moods=[MoodTag(m) for m in item.moods if m in MoodTag._value2member_map_],
                locale=item.locale,
            )
            for item in content.enriched_tracks
            if 0 <= item.track_index < len(tracks)
        ]
