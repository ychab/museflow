import json
from typing import Any
from typing import cast

from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.track import Track
from museflow.domain.enums import MoodTag
from museflow.domain.enums import TasteProfiler
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.exceptions import TasteProfilerRateLimitExceeded
from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TASTE_PROFILE_SCHEMA
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TasteProfileResponse
from museflow.infrastructure.config.settings.openrouter import LLMSettings


def _format_tracks(tracks: list[Track]) -> str:
    lines = []

    for track in tracks:
        first = track.played_at_first.date() if track.played_at_first else "?"
        last = track.played_at_last.date() if track.played_at_last else "?"
        artists = " & ".join(track.artists)
        score_part = f" | score:{track.score}" if track.score is not None else ""
        lines.append(
            f"first:{first} | last:{last} | plays:{track.played_count}{score_part} | {artists} - {track.name}"
        )

    return "\n".join(lines)


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
    def profiler_type(self) -> TasteProfiler:
        # Kept until the profiler enum is dropped: `playlist discover` looks the profile up by this value.
        return TasteProfiler.GEMINI

    @property
    def logic_version(self) -> str:
        return "v2.0"

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

    async def _complete(self, prompt: str, llm: LLMSettings) -> TasteProfileData:
        try:
            content = await self._client.complete(
                [ChatMessage(role="user", content=prompt)],
                response_model=TasteProfileResponse,
                schema=TASTE_PROFILE_SCHEMA,
                llm=llm,
                adapter="profiler",
            )
        except LLMRateLimitError as e:
            raise TasteProfilerRateLimitExceeded(str(e)) from e
        except LLMRequestError as e:
            raise TasteProfileBuildException(str(e)) from e
        except LLMResponseError as e:
            raise TasteProfileBuildException(f"Invalid taste profile response: {e}") from e

        return cast(TasteProfileData, content.model_dump())

    async def build_profile_segment(self, tracks: list[Track]) -> TasteProfileData:
        dates = [t.played_at_last for t in tracks if t.played_at_last]
        if dates:
            min_date = min(dates).date()
            max_date = max(dates).date()
            date_range = f"{min_date} to {max_date}"
        else:
            date_range = "unknown period"

        prompt = (
            f"Analyze these {len(tracks)} tracks from [{date_range}]. Build a musical taste profile segment.\n"
            "Return JSON with exactly these keys:\n"
            '- "taste_timeline": one TasteEra for this batch\n'
            '- "core_identity": [{"key": tag, "value": weight 0-1}] long-term affinity signals\n'
            '- "current_vibe": [{"key": tag, "value": weight 0-1}] what this batch reveals right now\n'
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
            f"\nTrack format: first=first listen date | last=last listen date | plays=total play count "
            f"| score=explicit user rating ({DISCOVERY_TRACK_SCORE_MIN}=actively disliked, {DISCOVERY_TRACK_SCORE_MAX}=loved, absent=not yet rated). "
            "Treat high-scored tracks as confirmed taste anchors; treat min-score tracks as anti-preferences; "
            "infer preference from play count for unrated tracks.\n"
            "\nTracks:\n"
            f"{_format_tracks(tracks)}"
        )
        return await self._complete(prompt, self._segment_llm)

    async def merge_profiles(self, foundation: TasteProfileData, new_segment: TasteProfileData) -> TasteProfileData:
        foundation_json = json.dumps(foundation, ensure_ascii=False)
        segment_json = json.dumps(new_segment, ensure_ascii=False)

        prompt = (
            "You are a precise data architect evolving a Master Taste Profile.\n\n"
            f"Existing profile (Foundation):\n{foundation_json}\n\n"
            f"New incoming data (Segment):\n{segment_json}\n\n"
            "Rules for merging:\n"
            "1. taste_timeline Logic:\n"
            "   - Compare the New Segment to the last Era in the Foundation.\n"
            "   - If they are >80% similar (moods match and technical_fingerprint values differ by <0.15 on average), "
            "MERGE them by updating the 'until' date of the last era.\n"
            "   - If they differ, add the New Segment as a new TasteEra.\n"
            "   - HARD CONSTRAINT: If the timeline exceeds 15 entries, merge the two oldest consecutive eras "
            "to keep the total timeline concise and avoid JSON bloat.\n\n"
            "2. core_identity (The DNA):\n"
            "   - If the Foundation is empty, initialize it with the Segment values.\n"
            "   - If not empty, calculate a weighted average: (Foundation * 0.7) + (Segment * 0.3).\n"
            "   - Ensure all keys from both Foundation and Segment are preserved or merged.\n"
            "   - Example: Foundation 'French Rap': 0.8 + Segment 'French Rap': 0.2 = 0.62.\n"
            "3. current_vibe:\n"
            "   - DISCARD foundation values. REPLACE entirely with the New Segment's vibe to reflect the current trajectory.\n\n"
            "4. Technical Integrity:\n"
            "   - Keep all existing 'technical_fingerprint' values in previous eras UNCHANGED.\n"
            "   - personality_archetype: keep null.\n"
            "   - life_phase_insights: keep empty.\n"
            "   - musical_identity_summary, behavioral_traits, discovery_style: keep null.\n\n"
            "For core_identity, current_vibe, and dominant_moods, use ONLY values from this exact vocabulary:\n"
            f"  Genres — macro: {', '.join(t.value for t in GENRE_MACRO_TAGS)}\n"
            f"         — meso:  {', '.join(t.value for t in GENRE_MESO_TAGS)}\n"
            f"         — micro: {', '.join(t.value for t in GENRE_MICRO_TAGS)}\n"
            f"  Moods: {', '.join(m.value for m in MoodTag)}\n"
            "Do NOT use any genre or mood label outside this vocabulary.\n"
            "Return the full merged JSON. Be mathematically precise and preserve all keys."
        )

        return await self._complete(prompt, self._merge_llm)

    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        profile_json = json.dumps(profile, ensure_ascii=False)

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

        return await self._complete(prompt, self._reflect_llm)
