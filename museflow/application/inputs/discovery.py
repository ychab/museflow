import uuid
from dataclasses import dataclass

from museflow.domain.types import DiscoveryFocus


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteConfigInput:
    """Configuration for the AI taste-driven discovery process.

    Attributes:
        focus: The discovery focus strategy.
        profile_name: Optional profile name; if omitted the latest profile is used.
        genre: Optional genre filter hint passed to the advisor agent.
        mood: Optional mood hint passed to the advisor agent.
        custom_instructions: Optional freeform instructions for the advisor agent.
        advisor_limit: Number of recommended tracks to request from the advisor.
        reconciler_limit: Maximum number of search candidates per suggestion.
        score_band_width: Width of advisor score bands for tiebreaking by reconciler confidence.
        playlist_limit: Target number of tracks in the generated playlist.
        max_attempts: Maximum number of advisor calls before stopping.
        max_tracks_per_artist: Maximum tracks per artist in the final playlist.
        liked_tracks_score_threshold: Minimum user score for a track to be sent to the advisor as a positive example.
        liked_tracks_limit: Maximum number of liked tracks to send (top-scored first).
        dry_run: If True, skip playlist creation.
    """

    focus: DiscoveryFocus = DiscoveryFocus.EXPANSION
    profile_name: str | None = None
    genre: str | None = None
    mood: str | None = None
    custom_instructions: str | None = None

    advisor_limit: int = 10
    reconciler_limit: int = 10
    playlist_limit: int = 10

    max_attempts: int = 5
    max_tracks_per_artist: int = 3

    score_band_width: float = 0.05

    liked_tracks_score_threshold: int = 7
    liked_tracks_limit: int = 200

    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class DiscoveryPlaylistRatingInput:
    track_id: uuid.UUID
    score: int


@dataclass(frozen=True, kw_only=True)
class BlacklistChoiceInput:
    track_name: str
    artist_name: str
    blacklist_track: bool
    blacklist_artist: bool
