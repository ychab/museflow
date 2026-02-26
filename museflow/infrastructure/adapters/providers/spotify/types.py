from enum import StrEnum
from typing import Literal

SpotifyTimeRange = Literal["short_term", "medium_term", "long_term"]


class SpotifyScope(StrEnum):
    """Spotify OAuth scopes for user-related operations.

    See: https://developer.spotify.com/documentation/web-api/concepts/scopes
    """

    # Listening History
    USER_READ_PLAYBACK_STATE = "user-read-playback-state"
    USER_MODIFY_PLAYBACK_STATE = "user-modify-playback-state"
    USER_READ_CURRENTLY_PLAYING = "user-read-currently-playing"

    # Spotify Connect
    STREAMING = "streaming"

    # Playlists
    PLAYLIST_READ_PRIVATE = "playlist-read-private"
    PLAYLIST_READ_COLLABORATIVE = "playlist-read-collaborative"
    PLAYLIST_MODIFY_PRIVATE = "playlist-modify-private"
    PLAYLIST_MODIFY_PUBLIC = "playlist-modify-public"

    # Follow
    USER_FOLLOW_MODIFY = "user-follow-modify"
    USER_FOLLOW_READ = "user-follow-read"

    # Playback
    USER_READ_PLAYBACK_POSITION = "user-read-playback-position"
    USER_TOP_READ = "user-top-read"
    USER_READ_RECENTLY_PLAYED = "user-read-recently-played"

    # Library
    USER_LIBRARY_MODIFY = "user-library-modify"
    USER_LIBRARY_READ = "user-library-read"

    # Users
    USER_READ_EMAIL = "user-read-email"
    USER_READ_PRIVATE = "user-read-private"

    @classmethod
    def required_scopes(cls) -> str:
        scopes = [
            cls.USER_TOP_READ,
            cls.USER_LIBRARY_READ,
            cls.PLAYLIST_READ_PRIVATE,
        ]
        return " ".join(scope.value for scope in scopes)
