import json
from typing import Any
from typing import cast

from pydantic import BaseModel

from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.const import TASTE_TIMELINE_MAX_ERAS
from museflow.domain.entities.taste import TasteEra
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.enums import MoodTag
from museflow.domain.exceptions import TasteProfileBuildError
from museflow.domain.exceptions import TasteProfilerRateLimitExceededError
from museflow.domain.utils.taste import merge_taste_profiles
from museflow.domain.value_objects.taste import ListeningPeriod
from museflow.domain.value_objects.taste import PeriodTrack
from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TASTE_PROFILE_SCHEMA
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TIMELINE_MERGE_SCHEMA
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TasteProfileResponse
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TimelineMergeResponse
from museflow.infrastructure.adapters.profilers.openrouter.schemas import split_weights
from museflow.infrastructure.config.settings.openrouter import LLMSettings

# Without it, labels leak the processing ("2025 Current Batch") or keep dates a later merge makes stale
_ERA_LABEL_RULE = (
    'era_label names the music of the era (e.g. "Late-Night French Rap"): never dates, years, or words about the '
    "data or its processing (batch, segment, current, period). Dates belong in time_range only, as "
    '"YYYY-MM-DD to YYYY-MM-DD".'
)


def _format_tracks(tracks: list[PeriodTrack]) -> str:
    lines = []

    for period_track in tracks:
        track = period_track.track
        artists = " & ".join(track.artists)
        score_part = f" | score:{track.score}" if track.score is not None else ""
        lines.append(f"plays:{period_track.plays}{score_part} | {artists} - {track.name}")

    return "\n".join(lines)


def _profile_json(profile: TasteProfileData) -> str:
    """Dumps a profile in the shape the response schema asks for, so the model reads what it must write back."""
    return json.dumps(
        {
            **profile,
            "core_identity": split_weights(profile["core_identity"]),
            "current_vibe": split_weights(profile["current_vibe"]),
        },
        ensure_ascii=False,
    )


def _era_json(era: TasteEra) -> str:
    return json.dumps(era, ensure_ascii=False)


def _step_metadata(llm: LLMSettings) -> dict[str, Any]:
    return {
        "model": llm.MODEL,
        "fallback_models": llm.FALLBACK_MODELS,
        "reasoning_effort": llm.REASONING_EFFORT,
        "max_tokens": llm.MAX_TOKENS,
        "temperature": llm.TEMPERATURE,
    }


class OpenRouterTasteProfileAdapter(OpenRouterAdapterMixin, TasteProfilerPort):
    """Adapter that builds a taste profile through OpenRouter, each step (segment, merge, reflect) with its own model."""

    def __init__(
        self,
        client: OpenRouterClient,
        segment_llm: LLMSettings,
        merge_llm: LLMSettings,
        reflect_llm: LLMSettings,
    ) -> None:
        super().__init__(client=client)
        self._segment_llm = segment_llm
        self._merge_llm = merge_llm
        self._reflect_llm = reflect_llm

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    @property
    def logic_version(self) -> str:
        return "v2.2"

    @property
    def profiler_metadata(self) -> dict[str, Any]:
        return {
            "gateway": "openrouter",
            "steps": {
                "segment": _step_metadata(self._segment_llm),
                "merge": _step_metadata(self._merge_llm),
                "reflect": _step_metadata(self._reflect_llm),
            },
        }

    async def _complete[T: BaseModel](
        self,
        prompt: str,
        response_model: type[T],
        schema: JsonSchemaProperty,
        llm: LLMSettings,
        step: str,
    ) -> T:
        try:
            content = await self._client.complete(
                [ChatMessage(role="user", content=prompt)],
                response_model=response_model,
                schema=schema,
                llm=llm,
                adapter=f"profiler {step}",
            )
        except LLMRateLimitError as e:
            raise TasteProfilerRateLimitExceededError(str(e)) from e
        except LLMRequestError as e:
            raise TasteProfileBuildError(str(e)) from e
        except LLMResponseError as e:
            raise TasteProfileBuildError(f"Invalid taste profile response: {e}") from e

        return content

    async def _complete_profile(self, prompt: str, llm: LLMSettings, step: str) -> TasteProfileData:
        content = await self._complete(prompt, TasteProfileResponse, TASTE_PROFILE_SCHEMA, llm, step)
        return cast(TasteProfileData, content.model_dump())

    async def build_profile_segment(self, period: ListeningPeriod) -> TasteProfileData:
        date_range = f"{period.start.date()} to {period.end.date()}"
        prompt = (
            f"Analyze these {len(period.tracks)} tracks, the most played from [{date_range}] "
            f"({period.plays} plays in this period). Build a musical taste profile segment.\n"
            "Return JSON with exactly these keys:\n"
            f'- "taste_timeline": one TasteEra covering these tracks, with time_range "{date_range}". '
            f"{_ERA_LABEL_RULE}\n"
            '- "core_identity": long-term affinity signals, as {"genre_macro": [{"key": tag, "value": weight 0-1}], '
            '"genre_meso": [...], "genre_micro": [...], "mood": [...]}, each tag in the list of its tier\n'
            '- "current_vibe": what this batch reveals right now, same shape as core_identity\n'
            '- "personality_archetype": null\n'
            '- "life_phase_insights": []\n'
            '- "musical_identity_summary", "behavioral_traits", "discovery_style": null\n'
            "\nFor core_identity, current_vibe, and dominant_moods, use ONLY values from this exact vocabulary:\n"
            f"  Genres — macro: {', '.join(t.value for t in GENRE_MACRO_TAGS)}\n"
            f"         — meso:  {', '.join(t.value for t in GENRE_MESO_TAGS)}\n"
            f"         — micro: {', '.join(t.value for t in GENRE_MICRO_TAGS)}\n"
            f"  Moods: {', '.join(m.value for m in MoodTag)}\n"
            "Do NOT use any genre or mood label outside this vocabulary.\n"
            "\nFor each TasteEra, populate technical_fingerprint by inferring numerical values (0.0 to 1.0) "
            "from the genres present in the batch. Use these genre-to-value guidelines:\n"
            "- energy: Trap/Metal/Punk → high (~0.8-0.9); Pop/Electronic → mid (~0.5-0.6); Ambient/Classical → low (~0.1-0.2)\n"
            "- acousticness: Acoustic/Folk/Classical → high (~0.8-0.9); Electronic/Synth → low (~0.05-0.2)\n"
            "- rhythmic_complexity: Jazz/Math-rock/Polyrhythmic → high (~0.8); 4/4 Pop/EDM → low (~0.2-0.4)\n"
            "- atmospheric: Ambient/Shoegaze/Post-rock → high (~0.8-0.9); Punk/Trap → low (~0.1-0.2)\n"
            "- instrumentalness: Instrumental/Classical/Jazz → high (~0.8-0.9); Rap/Pop with lyrics → low (~0.05-0.2)\n"
            f"\nTrack format: plays=play count during this period "
            f"| score=explicit user rating ({DISCOVERY_TRACK_SCORE_MIN}=actively disliked, {DISCOVERY_TRACK_SCORE_MAX}=loved, absent=not yet rated). "
            "Treat high-scored tracks as confirmed taste anchors; treat min-score tracks as anti-preferences; "
            "infer preference from play count for unrated tracks.\n"
            "\nTracks:\n"
            f"{_format_tracks(period.tracks)}"
        )
        return await self._complete_profile(prompt, self._segment_llm, "segment")

    async def merge_profiles(
        self,
        foundation: TasteProfileData,
        new_segment: TasteProfileData,
        segment_weight: float,
    ) -> TasteProfileData:
        # The code merges the weights and assembles the timeline: the model only takes the decisions that need
        # judgment, so it reads and writes a few eras instead of the whole profile.
        timeline = foundation["taste_timeline"]
        segment_eras = new_segment["taste_timeline"]
        if not timeline or not segment_eras:
            return merge_taste_profiles(
                foundation, new_segment, segment_weight=segment_weight, absorb=False, oldest_label=None
            )

        prompt = (
            "You are a precise music curator extending the taste timeline of a listener.\n\n"
            f"Last era of the timeline:\n{_era_json(timeline[-1])}\n\n"
            f"New era, from the next listening segment:\n{_era_json(segment_eras[0])}\n\n"
            "Return JSON with exactly these keys:\n"
            '- "absorb": true if the new era continues the last era: they are >80% similar (moods match and '
            "technical_fingerprint values differ by <0.15 on average) AND the last era's label already describes the "
            "new era's music. The last era is then extended to the new era's end date, its label unchanged: never "
            "count on a broader label. Otherwise false, and the new era is added to the timeline. When in doubt, "
            "answer false: the timeline should show distinct listening phases.\n"
        )
        if len(timeline) >= TASTE_TIMELINE_MAX_ERAS:
            prompt += (
                '- "oldest_label": the timeline is full, so if the new era is added, its two oldest eras become one:\n'
                f"{_era_json(timeline[0])}\n{_era_json(timeline[1])}\n"
                f"Name the era covering both. {_ERA_LABEL_RULE}\n"
            )
        else:
            prompt += '- "oldest_label": null\n'

        decision = await self._complete(prompt, TimelineMergeResponse, TIMELINE_MERGE_SCHEMA, self._merge_llm, "merge")
        return merge_taste_profiles(
            foundation,
            new_segment,
            segment_weight=segment_weight,
            absorb=decision.absorb,
            oldest_label=decision.oldest_label,
        )

    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        profile_json = _profile_json(profile)

        # Filter Triad for future playlist engine:
        # current_vibe + technical_fingerprint (from latest era) + behavioral_traits
        # → when given Mood + Genre inputs, cross-reference all three to generate tailored playlists
        # (e.g. "Focus" + "Electronic" → check atmospheric score + core urban roots → "Urban-Ambient")
        prompt = (
            "You have the complete Master Taste Profile of a listener across their entire library.\n\n"
            f"Profile:\n{profile_json}\n\n"
            "Perform a final psychographic reflection. Populate ALL of these fields:\n"
            '- "personality_archetype": one evocative label (e.g. "The Architect of Sound")\n'
            '- "life_phase_insights": list of observed life transitions\n'
            '  (e.g. "Shift from high-energy industrial to calming ambient during 2024")\n'
            '- "musical_identity_summary": 2-3 sentences in English describing the listener\'s '
            "musical evolution from the earliest to the most recent era. Be insightful and witty — "
            "capture the arc, not just the genres.\n"
            '- "behavioral_traits": object with float scores (0.0–1.0) for exactly these keys:\n'
            '  "openness" (willingness to explore new genres), '
            '"adventurousness" (rate of style shifts over time), '
            '"nostalgia_bias" (weight of older eras in current listening), '
            '"rhythmic_dependency" (how central rhythm/beat is vs. melody/texture)\n'
            '- "discovery_style": one short archetype label describing how this listener discovers music\n'
            '  (e.g. "The Digger", "The Loyalist", "The Trend-Hopper", "The Deep Diver")\n\n'
            "Return the full profile JSON with all five fields populated. Keep all other fields unchanged."
        )

        return await self._complete_profile(prompt, self._reflect_llm, "reflect")
