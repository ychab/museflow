from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.exceptions import AdvisorRateLimitExceededError
from museflow.domain.exceptions import DiscoveryTasteStrategyError
from museflow.domain.utils import taste as taste_utils
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_discovery_strategy
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_STRATEGY_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryStrategyResponse
from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.config.settings.openrouter import LLMSettings


class OpenRouterAdvisorAdapter(OpenRouterAdapterMixin, AdvisorPort):
    """Adapter that asks an LLM, through OpenRouter, for a discovery strategy matching a taste profile."""

    def __init__(self, client: OpenRouterClient, llm: LLMSettings) -> None:
        super().__init__(client=client)
        self._llm = llm

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    async def get_discovery_strategy(
        self,
        profile: TasteProfile,
        advisor_limit: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
        excluded_tracks: list[TrackSuggested] | None = None,
        known_tracks: list[TrackSuggested] | None = None,
        blacklisted_artists: list[str] | None = None,
        blacklisted_tracks: list[str] | None = None,
        liked_tracks: list[Track] | None = None,
        disliked_tracks: list[Track] | None = None,
        top_artists: dict[str, int] | None = None,
    ) -> DiscoveryTasteStrategy:
        data = profile.profile

        timeline_summary = taste_utils.timeline_summary(data)
        core_identity_str = taste_utils.core_identity_summary(data)
        current_vibe_str = taste_utils.current_vibe_summary(data)
        behavioral_traits_str = taste_utils.behavioral_traits_summary(data)
        archetype = taste_utils.personality_archetype(data)
        oldest_era = taste_utils.oldest_era_label(data)
        current_era = taste_utils.current_era_label(data)

        traits = data.get("behavioral_traits", {})
        openness = traits.get("openness", 0.5)
        adventurousness = traits.get("adventurousness", 0.5)
        if openness < 0.4 and adventurousness < 0.4:
            risk_calibration = (
                "User prefers sonic comfort zones — stay close to established core identity. No genre leaps."
            )
        elif openness > 0.7 or adventurousness > 0.7:
            risk_calibration = "User is adventurous — push into niche, adjacent, or crossover territory confidently."
        else:
            risk_calibration = "User is moderately open — occasional adjacent genre exploration is fine, but anchor to known strengths."

        focus_descriptions = {
            DiscoveryFocus.EXPANSION: "Find high-probability cousin genres not yet explored.",
            DiscoveryFocus.ROOTS_REVIVAL: f"Find modern tracks replicating the technical fingerprint of the oldest era ({oldest_era}).",
            DiscoveryFocus.CULTURAL_BRIDGE: f"Find music at the intersection of {oldest_era} and {current_era}.",
        }

        focus_block = ""
        if focus:
            focus_block = f"### FOCUS STRATEGY: {focus.value}\n{focus_descriptions[focus]}\n\n"

        exclusion_parts: list[str] = []
        if excluded_tracks:
            formatted = "\n".join(f"- {t.primary_artist}: {t.name}" for t in excluded_tracks)
            exclusion_parts.append(
                "### EXCLUSION LIST (DO NOT SUGGEST THESE)\n"
                "These tracks have already been considered in this session. "
                "You MUST suggest DIFFERENT tracks and avoid these artists where possible:\n"
                f"{formatted}"
            )
        if known_tracks:
            formatted = "\n".join(f"- {t.primary_artist}: {t.name}" for t in known_tracks)
            exclusion_parts.append(
                "### ALREADY KNOWN BY THE USER (DO NOT SUGGEST THESE)\n"
                "These suggestions of this session were already in the user's library: the picks were too obvious. "
                "Dig deeper: lesser-known artists, deep cuts, less mainstream tracks:\n"
                f"{formatted}"
            )
        if top_artists:
            formatted = "\n".join(f"- {artist} ({count} tracks)" for artist, count in top_artists.items())
            exclusion_parts.append(
                "### TOP ARTISTS IN THE LIBRARY\n"
                "The user already owns many tracks of these artists (count in brackets): their well-known tracks "
                "are already known. A rare deep cut of theirs is still welcome, but most picks should come from "
                "other artists:\n"
                f"{formatted}"
            )
        if blacklisted_artists:
            formatted = "\n".join(f"- {a}" for a in blacklisted_artists)
            exclusion_parts.append(
                "### PERMANENTLY BLACKLISTED ARTISTS (NEVER SUGGEST)\n"
                "The user has permanently excluded these artists. Do NOT suggest any track by them:\n"
                f"{formatted}"
            )
        if blacklisted_tracks:
            formatted = "\n".join(f"- {t}" for t in blacklisted_tracks)
            exclusion_parts.append(
                "### PERMANENTLY BLACKLISTED TRACKS (NEVER SUGGEST)\n"
                "The user has permanently excluded these tracks:\n"
                f"{formatted}"
            )
        exclusion_block = ("\n\n".join(exclusion_parts) + "\n\n") if exclusion_parts else ""

        # The liked anchors are the global top, not filtered on the prompt: a free-text theme does not map to the
        # enriched genres without interpreting it, so the advisor picks the relevant anchors itself (#146). If the
        # playlists drift off theme, filter them here (see #137).
        liked_tracks_block = ""
        if liked_tracks:
            formatted = "\n".join(f"- {t.artists[0] if t.artists else 'Unknown'}: {t.name}" for t in liked_tracks)
            liked_tracks_block = (
                "### LIKED TRACKS\n"
                "These are tracks the user has explicitly enjoyed and rated highly. "
                "Use them as concrete taste anchors when shaping your recommendations — "
                "they reveal what this user genuinely responds to beyond statistical patterns.\n"
                f"{formatted}\n\n"
            )

        disliked_tracks_block = ""
        if disliked_tracks:
            formatted = "\n".join(f"- {t.artists[0] if t.artists else 'Unknown'}: {t.name}" for t in disliked_tracks)
            disliked_tracks_block = (
                "### DISLIKED TRACKS\n"
                "These are tracks the user rated low. Steer away from what they share (sound, style, production), "
                "not only from these exact tracks.\n"
                f"{formatted}\n\n"
            )

        system_prompt = (
            "### ROLE\n"
            'You are the "MuseFlow Navigator," a world-class musicologist.\n'
            "Your goal: recommend NEW music the user has never heard, based on their Taste Profile.\n\n"
            f"### USER IDENTITY: {archetype}\n"
            f"- Core Identity: {core_identity_str}\n"
            f"- Current Active Vibe: {current_vibe_str}\n"
            f"- Behavioral Traits: {behavioral_traits_str}\n"
            f"- Taste Timeline (oldest → newest): {timeline_summary}\n\n"
            "### RISK CALIBRATION\n"
            f"{risk_calibration}\n\n"
            f"{exclusion_block}"
            f"{liked_tracks_block}"
            f"{disliked_tracks_block}"
            f"{focus_block}"
            "### CONSTRAINTS\n"
            "- Return ONLY the JSON object (schema enforced).\n"
            "- recommended_tracks MUST be tracks the user has NOT heard before — they are new discoveries.\n"
            "- recommended_tracks MUST NOT appear in any exclusion or blacklist section above.\n"
            "- A user request, when given, sets the playlist theme: every recommended track MUST fit it.\n"
            "- If exclusions are provided, pivot to deeper cuts or adjacent artists to ensure variety.\n"
            "- Every recommended track MUST be a real, released recording you are certain exists in the streaming\n"
            "  catalogues. Never invent or guess a title: if you are unsure a song exists, pick another one.\n"
            "- Give each track's exact released title, without version suffixes (Remix, Radio Edit, Live) unless that\n"
            "  version is the pick, and its artists as credited, primary artist first.\n"
            f"- Provide up to {advisor_limit} recommended tracks, each with a discovery score (0.0–1.0).\n"
            "- Quality over quantity: only include a track if your confidence score would be ≥ 0.7.\n"
            "  If you only have 5 high-confidence picks, return 5 — do not pad with uncertain ones.\n"
            "  Score interpretation: 0.9+ = near-certain fit; 0.7–0.9 = solid pick; below 0.7 = omit.\n"
            "- Keep suggested_playlist_name creative and thematic.\n"
        )

        user_parts: list[str] = []
        if focus:
            user_parts.append(f"Apply the '{focus.value}' focus strategy.")
        if prompt:
            user_parts.append(f"User request: {prompt}")
        user_message = " ".join(user_parts) or "Recommend new tracks for this user."

        try:
            content = await self._client.complete(
                [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_message),
                ],
                response_model=DiscoveryStrategyResponse,
                schema=DISCOVERY_STRATEGY_SCHEMA,
                llm=self._llm,
                adapter="advisor",
            )
        except LLMRateLimitError as e:
            raise AdvisorRateLimitExceededError(str(e)) from e
        except LLMRequestError as e:
            raise DiscoveryTasteStrategyError(str(e)) from e
        except LLMResponseError as e:
            raise DiscoveryTasteStrategyError(f"Invalid discovery strategy response: {e}") from e

        return to_discovery_strategy(content)
