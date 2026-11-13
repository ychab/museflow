import logging

from pydantic import BaseModel

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.exceptions import AdvisorRateLimitExceededError
from museflow.domain.exceptions import DiscoveryTasteStrategyError
from museflow.domain.utils import taste as taste_utils
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_discovery_artist_strategy
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_tracks_picked
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_ARTISTS_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_PICKS_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryArtistsResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryPicksResponse
from museflow.infrastructure.adapters.common.llm.adapter import OpenRouterAdapterMixin
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMResponseError
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.config.settings.openrouter import LLMSettings

logger = logging.getLogger(__name__)


class OpenRouterAdvisorAdapter(OpenRouterAdapterMixin, AdvisorPort):
    """Adapter that asks an LLM, through OpenRouter, for artists matching a taste profile, then for picks."""

    def __init__(self, client: OpenRouterClient, llm: LLMSettings) -> None:
        super().__init__(client=client)
        self._llm = llm

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    async def get_discovery_artists(
        self,
        profile: TasteProfile,
        artists_limit: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
        excluded_artists: list[str] | None = None,
        blacklisted_artists: list[str] | None = None,
        blacklisted_tracks: list[str] | None = None,
        liked_tracks: list[Track] | None = None,
        disliked_tracks: list[Track] | None = None,
        covered_artists: dict[str, int] | None = None,
    ) -> DiscoveryArtistStrategy:
        exclusion_parts: list[str] = []
        if excluded_artists:
            formatted = "\n".join(f"- {artist}" for artist in excluded_artists)
            exclusion_parts.append(
                "### EXCLUSION LIST (DO NOT SUGGEST THESE)\n"
                "These artists have already been considered in this session. You MUST suggest DIFFERENT artists:\n"
                f"{formatted}"
            )
        exclusion_parts.extend(self._library_exclusion_parts(covered_artists, blacklisted_artists, blacklisted_tracks))

        # With a request, the profile still leads, except on what the request settles: the sound it implies, and the
        # artists when it names a genre with its own sound (#177). Without a stated language, the profile's languages
        # no longer break ties: they brought in artists of the user's usual scene, given a made-up genre sound (#184).
        # An artist the request names is either the request itself, uncapped and searched deeper, or a sound reference
        # kept out (#200).
        request_block = ""
        if prompt:
            request_block = (
                "### USER REQUEST VS TASTE PROFILE\n"
                "The user request narrows the profile; it does not replace it.\n"
                "- First read what the request implies about the SOUND: energy, tempo, mood, texture, production\n"
                "  (e.g. 'cloud rap' implies hazy, floating, low energy; 'workout' implies high energy). A request\n"
                "  naming only a genre, a scene, a language or a region (e.g. 'US rap', 'French rap') implies nothing\n"
                "  about the sound.\n"
                "- Where the request implies a sound dimension, it wins over the profile on that dimension ONLY: set\n"
                "  aside any trait, vibe or liked track that pulls the other way (e.g. a high-energy profile asking for\n"
                "  cloud rap gets floating, low-energy tracks, not energetic ones).\n"
                "- A requested genre with its own sound (e.g. cloud rap, ambient, drill) decides WHO can be suggested:\n"
                "  only artists whose core sound IS that genre. Never an artist of the user's usual scene who merely\n"
                "  sits next to it: a rapper with no cloud sound is no cloud rap artist, however close to the profile.\n"
                "- A language or region counts only when the request states it. Never infer one from the wording or\n"
                "  the language of the request (e.g. 'rap cloud' written in French does not ask for French artists).\n"
                "  Without one stated, the profile's languages never choose an artist: one who fits the genre fully\n"
                "  beats one who fits it less but shares the user's language.\n"
                "- The pioneers and best-known artists of a requested genre are likely known to the user already:\n"
                "  favour the next generation, the lesser-known and the international scenes of that genre.\n"
                "- Everything else still comes from the profile: the scenes, eras and production the user loves, the\n"
                "  dislikes, the risk calibration. A request with no sound implication is answered from the profile\n"
                "  entirely.\n"
                "- In the reasoning, name each profile dimension you set aside because the request overrides it, or\n"
                "  say that none was.\n\n"
                "### ARTISTS NAMED IN THE REQUEST\n"
                "Read what the wording asks of each artist the request names:\n"
                "- The request asks for the artist's OWN tracks (e.g. 'tracks of Artist X I don't know', 'more from\n"
                "  Artist X', 'Artist X deep cuts'): the artist IS the request. Recommend them with `requested` true,\n"
                "  even when the library already covers them: the user wants their tracks they have not heard yet.\n"
                "  A request naming only such artists gets ONLY them: no other artist. Once they are all in the\n"
                "  exclusion list, return no artist at all.\n"
                "- The request uses the artist as a REFERENCE (e.g. 'something that sounds like Artist X', 'in the\n"
                "  vein of Artist X'): the artist is the sound wanted, not the playlist. Never recommend them: suggest\n"
                "  other artists with that sound, `requested` false.\n\n"
            )

        constraints = (
            f"{request_block}"
            "### CONSTRAINTS\n"
            "- Return ONLY the JSON object (schema enforced).\n"
            "- Recommend ARTISTS, not tracks: their real tracks are fetched from the streaming catalogue afterwards,\n"
            "  and a second step chooses among them. Do not name any track.\n"
            "- recommended_artists MUST have tracks the user has NOT heard before — they are new discoveries.\n"
            "- recommended_artists MUST NOT appear in any exclusion or blacklist section above.\n"
            "- `requested` is true ONLY for an artist whose own tracks the user request asks for; false for every\n"
            "  other artist, and always false without a user request.\n"
            "- A user request, when given, sets the playlist theme: every recommended artist MUST have tracks that\n"
            "  fit it.\n"
            "- Every artist MUST be real and present in the streaming catalogues: give the name exactly as credited.\n"
            "- For each artist, `sound` describes in one sentence the tracks wanted from them for this playlist\n"
            "  (era, mood, tempo, texture, style): it guides the choice among their catalogue tracks.\n"
            f"- Provide up to {artists_limit} recommended artists, each with a discovery score (0.0–1.0).\n"
            "- Quality over quantity: only include an artist if your confidence score would be ≥ 0.7.\n"
            "  Score interpretation: 0.9+ = near-certain fit; 0.7–0.9 = solid pick; below 0.7 = omit.\n"
            "- Keep suggested_playlist_name creative and thematic.\n"
        )
        content = await self._complete(
            system_prompt=self._profile_system_prompt(
                profile, focus, exclusion_parts, liked_tracks, disliked_tracks, constraints
            ),
            user_message=self._user_message(prompt, focus, default="Recommend new artists for this user."),
            response_model=DiscoveryArtistsResponse,
            schema=DISCOVERY_ARTISTS_SCHEMA,
            step="advisor_artists",
        )
        return to_discovery_artist_strategy(content)

    async def pick_discovery_tracks(
        self,
        strategy: DiscoveryArtistStrategy,
        candidates: dict[str, list[Track]],
        tracks_limit: int,
        max_tracks_per_artist: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
    ) -> list[TrackPicked]:
        sounds = {artist.name: artist.sound for artist in strategy.artists}
        artists_requested = {artist.name for artist in strategy.artists if artist.requested}
        # Short ids instead of titles: the reply can only point at a listed track, never write a new one.
        candidates_by_id: dict[str, Track] = {}
        artist_blocks: list[str] = []
        for artist, tracks in candidates.items():
            lines: list[str] = []
            for track in tracks:
                track_id = str(len(candidates_by_id) + 1)
                candidates_by_id[track_id] = track
                album = track.album_name or "?"
                year = track.album_year or "?"
                lines.append(f"- {track_id} | {track.name} | {album} | {year}")
            requested = " (REQUESTED)" if artist in artists_requested else ""
            artist_blocks.append(
                f"#### {artist}{requested}\nWanted sound: {sounds.get(artist, '')}\n" + "\n".join(lines)
            )

        focus_line = f"- Focus strategy: {focus.value}\n" if focus else ""
        system_prompt = (
            "### ROLE\n"
            'You are the "MuseFlow Navigator," a world-class musicologist curating a playlist.\n'
            "You chose the artists below for this user; their real catalogue tracks the user does not know yet are\n"
            "listed under each one. Now choose the tracks.\n\n"
            "### YOUR STRATEGY\n"
            f"- {strategy.strategy_label}: {strategy.reasoning}\n"
            f"{focus_line}\n"
            "### CANDIDATES (id | title | album | album release year)\n" + "\n\n".join(artist_blocks) + "\n\n"
            "### CONSTRAINTS\n"
            "- Return ONLY the JSON object (schema enforced).\n"
            "- Pick ONLY ids listed above: any other id is discarded.\n"
            "- A user request, when given, sets the playlist theme: every pick MUST fit it, and the artist's wanted\n"
            "  sound.\n"
            "- Where the request implies a sound (energy, tempo, mood), it wins over the strategy above on that point:\n"
            "  a track that fits the strategy but not the requested sound is left out.\n"
            "- Judge each track by its SOUND (production, mood, flow, the artist's style on that album and in that\n"
            "  year), never by its words: a title or album name that echoes the theme (e.g. 'rain', 'night' for a\n"
            "  rainy-night request) is no evidence of fit, and a track does not need one.\n"
            "- A track you don't know: place it by its album and year in the artist's career. When you can't tell\n"
            "  how it sounds, leave it out.\n"
            f"- Pick up to {tracks_limit} tracks, at most {max_tracks_per_artist} per artist, featured appearances\n"
            "  included (a track crediting two artists counts for both): spread the picks across the artists.\n"
            "- An artist marked (REQUESTED) is one whose own tracks the user asked for: no per-artist limit, pick as\n"
            "  many of their tracks as fit. Their original tracks only: leave out remixes, live, acoustic, sped-up\n"
            "  or slowed versions and re-recordings, as the user likely knows the original.\n"
            "- Quality over quantity: pick fewer tracks, or none of an artist, when nothing fits — never pad.\n"
            f"  {tracks_limit} is a ceiling, not a target: a short list is a valid answer, as the app then runs\n"
            "  another round with other artists. A track off the requested sound is worse than no track.\n"
            "- Avoid two versions of the same song (remix, live, edit) unless that version is the better fit.\n"
            "- Give each pick a fit score (0.0–1.0): 0.9+ = near-certain fit; 0.7–0.9 = solid pick; below 0.7 = omit.\n"
        )
        content = await self._complete(
            system_prompt=system_prompt,
            user_message=self._user_message(prompt, focus, default="Choose the tracks for this playlist."),
            response_model=DiscoveryPicksResponse,
            schema=DISCOVERY_PICKS_SCHEMA,
            step="advisor_picks",
        )
        tracks_picked = to_tracks_picked(content, candidates_by_id)
        if len(tracks_picked) < len(content.picks):
            logger.warning(
                f"Picks dropped, not among the candidates or picked twice: {len(content.picks) - len(tracks_picked)}",
                extra={"returned": len(content.picks), "kept": len(tracks_picked)},
            )
        return tracks_picked

    async def _complete[T: BaseModel](
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        schema: JsonSchemaProperty,
        step: str,
    ) -> T:
        try:
            return await self._client.complete(
                [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_message),
                ],
                response_model=response_model,
                schema=schema,
                llm=self._llm,
                adapter=step,
            )
        except LLMRateLimitError as e:
            raise AdvisorRateLimitExceededError(str(e)) from e
        except LLMRequestError as e:
            raise DiscoveryTasteStrategyError(str(e)) from e
        except LLMResponseError as e:
            raise DiscoveryTasteStrategyError(f"Invalid discovery strategy response: {e}") from e

    @staticmethod
    def _profile_system_prompt(
        profile: TasteProfile,
        focus: DiscoveryFocus | None,
        exclusion_parts: list[str],
        liked_tracks: list[Track] | None,
        disliked_tracks: list[Track] | None,
        constraints: str,
    ) -> str:
        """The advisor's prompt around the taste profile, for the artists step."""
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

        return (
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
            f"{constraints}"
        )

    @staticmethod
    def _library_exclusion_parts(
        covered_artists: dict[str, int] | None,
        blacklisted_artists: list[str] | None,
        blacklisted_tracks: list[str] | None,
    ) -> list[str]:
        parts: list[str] = []
        if covered_artists:
            formatted = "\n".join(f"- {artist} ({count} tracks)" for artist, count in covered_artists.items())
            parts.append(
                "### ARTISTS ALREADY COVERED IN THE LIBRARY\n"
                "The user already owns many tracks of these artists (count in brackets): their well-known tracks "
                "are already known. A rare deep cut of theirs is still welcome, but most picks should come from "
                "other artists, unless the user request asks for one of these artists' own tracks:\n"
                f"{formatted}"
            )
        if blacklisted_artists:
            formatted = "\n".join(f"- {a}" for a in blacklisted_artists)
            parts.append(
                "### PERMANENTLY BLACKLISTED ARTISTS (NEVER SUGGEST)\n"
                "The user has permanently excluded these artists. Do NOT suggest any track by them:\n"
                f"{formatted}"
            )
        if blacklisted_tracks:
            formatted = "\n".join(f"- {t}" for t in blacklisted_tracks)
            parts.append(
                "### PERMANENTLY BLACKLISTED TRACKS (NEVER SUGGEST)\n"
                "The user has permanently excluded these tracks:\n"
                f"{formatted}"
            )
        return parts

    @staticmethod
    def _user_message(prompt: str | None, focus: DiscoveryFocus | None, default: str) -> str:
        user_parts: list[str] = []
        if focus:
            user_parts.append(f"Apply the '{focus.value}' focus strategy.")
        if prompt:
            user_parts.append(f"User request: {prompt}")
        return " ".join(user_parts) or default
