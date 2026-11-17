from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CreateExplorationPlaylistConfigInput:
    """Configuration for exploring the catalogue of the artists the user already knows.

    Attributes:
        prompt: Optional request on the sound wanted, in the user's words; the artists still come from their data.
        title: Optional playlist name, used as is; if omitted the playlist is named `Explore` with a timestamp.
        artists_limit: The favourite artists the rounds draw from, best first; shuffled, so that two runs do not start
            with the same artists.
        artists_per_attempt: The favourite artists searched per round.
        ratings_confidence: Bayesian confidence constant ranking the favourites: an artist with fewer rated tracks
            than this is pulled toward the user's mean rating.
        picks_limit: Tracks the advisor may pick per round, above `playlist_limit` as the per-artist cap and short
            replies eat into them.
        catalogue_tracks_pages: Search pages per query of an artist's catalogue search.
        artist_tracks_concurrency: Artists whose catalogue is searched at the same time, few enough for the provider
            not to rate limit the run.
        playlist_limit: Target number of tracks in the generated playlist.
        max_attempts: Maximum number of rounds before stopping.
        max_tracks_per_artist: Maximum tracks per credited artist in the final playlist.
        liked_tracks_score_threshold: Minimum user score for a track to be shown to the advisor as one the user loves.
        liked_tracks_limit: Maximum number of liked tracks read (top-scored first), before they are split per artist.
        dry_run: If True, skip playlist creation.
    """

    prompt: str | None = None
    title: str | None = None

    artists_limit: int = 20
    artists_per_attempt: int = 5
    ratings_confidence: int = 5

    picks_limit: int = 15
    catalogue_tracks_pages: int = 10
    artist_tracks_concurrency: int = 4
    playlist_limit: int = 10

    max_attempts: int = 3
    max_tracks_per_artist: int = 3

    liked_tracks_score_threshold: int = 7
    liked_tracks_limit: int = 200

    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.artist_tracks_concurrency < 1:
            raise ValueError("artist_tracks_concurrency must be at least 1")
        if self.artists_limit < 1:
            raise ValueError("artists_limit must be at least 1")
        if self.artists_per_attempt < 1:
            raise ValueError("artists_per_attempt must be at least 1")
