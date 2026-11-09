from dataclasses import dataclass

from museflow.domain.enums import DiscoveryFocus


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteConfigInput:
    """Configuration for the AI taste-driven discovery process.

    Attributes:
        prompt: Optional freeform request for the advisor (genres, moods, themes, in the user's words).
        focus: The discovery focus strategy. Without a prompt it defaults to `expansion`; with a prompt it stays
            unset unless given, as a focus would pull the advisor away from the requested theme.
        profile_name: Optional profile name; if omitted the latest profile is used.
        advisor_limit: Number of recommended tracks to request from the advisor.
        reconciler_limit: Maximum number of search candidates per suggestion.
        score_band_width: Width of advisor score bands for tiebreaking by reconciler confidence.
        playlist_limit: Target number of tracks in the generated playlist.
        max_attempts: Maximum number of advisor calls before stopping.
        max_tracks_per_artist: Maximum tracks per artist in the final playlist.
        liked_tracks_score_threshold: Minimum user score for a track to be sent to the advisor as a positive example.
        liked_tracks_limit: Maximum number of liked tracks to send (top-scored first).
        disliked_tracks_score_threshold: Maximum user score for a track to be sent to the advisor as a negative example.
        disliked_tracks_limit: Maximum number of disliked tracks to send (lowest-scored first).
        covered_artists_limit: Maximum number of artists the user owns the most tracks of to send (0 sends none).
        dry_run: If True, skip playlist creation.
    """

    prompt: str | None = None
    focus: DiscoveryFocus | None = None
    profile_name: str | None = None

    advisor_limit: int = 15
    reconciler_limit: int = 10
    playlist_limit: int = 10

    max_attempts: int = 3
    max_tracks_per_artist: int = 3

    score_band_width: float = 0.05

    liked_tracks_score_threshold: int = 7
    liked_tracks_limit: int = 200

    disliked_tracks_score_threshold: int = 2
    disliked_tracks_limit: int = 50

    covered_artists_limit: int = 100

    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.focus is None and not self.prompt:
            object.__setattr__(self, "focus", DiscoveryFocus.EXPANSION)
