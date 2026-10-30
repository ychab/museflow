import json
import logging

from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.value_objects.track import TrackEnrichment
from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.enrichers.openrouter.schemas import EnrichmentResponse
from museflow.infrastructure.adapters.enrichers.openrouter.schemas import build_enrichment_schema
from museflow.infrastructure.config.settings.openrouter import LLMSettings

logger = logging.getLogger(__name__)


class OpenRouterTrackEnricherAdapter(OpenRouterAdapterMixin, TrackEnricherPort):
    """Adapter that infers genre, mood and locale metadata for tracks through OpenRouter."""

    def __init__(self, client: OpenRouterClient, llm: LLMSettings) -> None:
        super().__init__(client=client)
        self._llm = llm

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
                "### LOCALES RULE\n"
                "- `locales`: list of 2-letter ISO 639-1 codes of **every language sung in the track** "
                "(lyrics language, not artist nationality). Return several codes when the lyrics mix languages "
                "(e.g. a duet).\n"
                "- Use signals in priority order:\n"
                "  1. Title script: non-Latin characters are strong evidence "
                "(Hangul → ko, Cyrillic → ru/uk/bg, Arabic script → ar/fa, "
                "CJK → zh/ja, Hebrew → he, Thai → th, Devanagari → hi).\n"
                "  2. Title vocabulary: recognisable non-English words in the title "
                "(French articles/prepositions, Spanish, Portuguese, Italian, German, Arabic words, etc.).\n"
                "  3. Artist cultural context: use as fallback when the title gives no language signal.\n"
                "- Return an empty list ONLY when: (a) the track appears instrumental (no lyrics), "
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
        tracks_json = json.dumps(
            [
                {"index": i, "title": track.name, "primary_artist": track.primary_artist}
                for i, track in enumerate(tracks)
            ],
            ensure_ascii=False,
        )
        try:
            content = await self._client.complete(
                [
                    ChatMessage(role="system", content=self._build_system_prompt(fields)),
                    ChatMessage(role="user", content=tracks_json),
                ],
                response_model=EnrichmentResponse,
                schema=build_enrichment_schema(fields),
                llm=self._llm,
                adapter="enricher",
            )
        except LLMResponseError as e:
            logger.exception("Invalid LLM enrichment response", extra={"failure_kind": e.failure_kind.value})
            return []

        return [
            TrackEnrichment(
                track_id=tracks[item.track_index].id,
                genres=[GenreTag(g) for g in item.genres if g in GenreTag._value2member_map_],
                moods=[MoodTag(m) for m in item.moods if m in MoodTag._value2member_map_],
                locales=item.locales,
            )
            for item in content.enriched_tracks
            if 0 <= item.track_index < len(tracks)
        ]
