import json
import logging

from pydantic import HttpUrl
from pydantic import ValidationError

from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.value_objects.track import TrackEnrichment
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.enrichers.gemini.schemas import GeminiEnrichmentResponse
from museflow.infrastructure.adapters.enrichers.gemini.schemas import build_enrichment_config
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

    @staticmethod
    def _build_system_prompt(fields: frozenset[EnrichField]) -> str:
        parts = [
            "### ROLE\nYou are a music metadata expert. For each provided track, classify its requested fields.\n"
        ]

        if EnrichField.GENRE in fields:
            parts.append(
                "### GENRE RULES\n"
                "Return 2 to 3 genre tags per track, ordered from broadest to most specific.\n"
                "Use ONLY values from the lists below — no synonyms, no paraphrases.\n\n"
                f"genres[0] — macro (pick ONE): {', '.join(t.value for t in GENRE_MACRO_TAGS)}\n\n"
                f"genres[1] — meso (pick ONE that fits the macro): {', '.join(t.value for t in GENRE_MESO_TAGS)}\n\n"
                f"genres[2] — micro (pick ONE or omit if none applies): {', '.join(t.value for t in GENRE_MICRO_TAGS)}\n\n"
                "Do NOT include artist names or track names as genres.\n"
            )

        if EnrichField.MOOD in fields:
            parts.append(
                "### MOOD RULES\n"
                f"- Return 1 to 2 mood labels chosen ONLY from this exact vocabulary: {', '.join(m.value for m in MoodTag)}.\n"
                "- Do NOT use any mood word outside this list.\n"
            )

        if EnrichField.LOCALE in fields:
            parts.append(
                "### LOCALE RULE\n"
                "- `locale`: 2-letter ISO 639-1 code for the **language the track is sung in** "
                "(lyrics language, not artist nationality).\n"
                "- Use signals in priority order:\n"
                "  1. Title script: non-Latin characters are strong evidence "
                "(Hangul → ko, Cyrillic → ru/uk/bg, Arabic script → ar/fa, "
                "CJK → zh/ja, Hebrew → he, Thai → th, Devanagari → hi).\n"
                "  2. Title vocabulary: recognisable non-English words in the title "
                "(French articles/prepositions, Spanish, Portuguese, Italian, German, Arabic words, etc.).\n"
                "  3. Artist cultural context: use as fallback when the title gives no language signal.\n"
                "- Omit ONLY when: (a) the track appears instrumental (no lyrics), "
                "or (b) none of the above signals give you reasonable confidence.\n"
                "- Do NOT conflate artist nationality with lyrics language "
                "(e.g. a French artist singing in English → en).\n"
            )

        parts.append(
            "\n### OUTPUT\n"
            "Return only the JSON object (schema enforced). "
            "Use the track_index field to match each result back to the input track."
        )

        return "\n".join(parts)

    async def enrich_tracks(self, tracks: list[Track], fields: frozenset[EnrichField]) -> list[TrackEnrichment]:
        request = GeminiGenerateContentRequest(
            system_instruction=GeminiRequestContent(
                parts=[GeminiRequestPart(text=self._build_system_prompt(fields))],
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
            generationConfig=build_enrichment_config(fields),
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
