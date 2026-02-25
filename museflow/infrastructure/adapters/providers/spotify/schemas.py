from collections.abc import Sequence
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from enum import StrEnum
from typing import Annotated
from typing import Literal

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl
from pydantic import NonNegativeInt
from pydantic import computed_field

from museflow.domain.entities.auth import OAuthProviderTokenState

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


class SpotifyToken(BaseModel):
    token_type: str
    access_token: str
    refresh_token: str | None = None  # Sometimes refresh token isn't returned on refresh
    expires_in: NonNegativeInt

    @computed_field
    def expires_at(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.expires_in)

    def to_domain(self, existing_refresh_token: str | None = None) -> OAuthProviderTokenState:
        refresh_token = self.refresh_token or existing_refresh_token
        if not refresh_token:
            raise ValueError("Refresh token is missing from both response and existing state.")

        return OAuthProviderTokenState(
            token_type=self.token_type,
            access_token=self.access_token,
            refresh_token=refresh_token,
            expires_at=self.expires_at,
        )


class SpotifyTrackArtist(BaseModel):
    id: str
    name: str


class SpotifyItem(BaseModel):
    id: str
    name: str
    href: HttpUrl


class SpotifyPlaylist(SpotifyItem):
    pass


class SpotifyArtist(SpotifyItem):
    popularity: int
    genres: list[str]


class SpotifyTrack(SpotifyItem):
    popularity: int
    artists: list[SpotifyTrackArtist]


class SpotifySavedTrack(BaseModel):
    added_at: AwareDatetime | None = None
    track: SpotifyTrack


class SpotifyPlaylistTrack(BaseModel):
    item: SpotifyTrack


class SpotifyPage[T: SpotifyItem | SpotifySavedTrack | SpotifyPlaylistTrack](BaseModel):
    items: Sequence[T]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=0)]
    offset: Annotated[int, Field(ge=0)]


class SpotifyPlaylistPage(SpotifyPage[SpotifyPlaylist]): ...


class SpotifySavedTrackPage(SpotifyPage[SpotifySavedTrack]): ...


class SpotifyPlaylistTrackPage(SpotifyPage[SpotifyPlaylistTrack]): ...


class SpotifyTopArtistPage(SpotifyPage[SpotifyArtist]): ...


class SpotifyTopTrackPage(SpotifyPage[SpotifyTrack]): ...
