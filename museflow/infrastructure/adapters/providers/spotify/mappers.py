import uuid
from typing import Any

from museflow.domain.entities.music import Album
from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.types import AlbumType
from museflow.domain.types import MusicProvider
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyAlbum
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyArtist
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyPlaylist
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyToken
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyTrack


def to_domain_token_payload(
    spotify_token: SpotifyToken, existing_refresh_token: str | None = None
) -> OAuthProviderTokenPayload:
    """Converts a SpotifyToken schema object to a domain OAuthProviderTokenPayload.

    This function maps the raw token data received from Spotify into the application's
    domain representation, ensuring that a refresh token is always present.
    """
    refresh_token = spotify_token.refresh_token or existing_refresh_token
    if not refresh_token:
        raise ValueError("Refresh token is missing from both response and existing state.")

    return OAuthProviderTokenPayload(
        token_type=spotify_token.token_type,
        access_token=spotify_token.access_token,
        refresh_token=refresh_token,
        expires_at=spotify_token.expires_at,  # type: ignore[arg-type]
    )


def to_domain_artist(
    spotify_artist: SpotifyArtist,
    user_id: uuid.UUID,
    is_top: bool = False,
    is_saved: bool = False,
    position: int | None = None,
) -> Artist:
    """Converts a SpotifyArtist schema object to a domain Artist entity."""
    return Artist(
        user_id=user_id,
        name=spotify_artist.name,
        popularity=spotify_artist.popularity,
        is_saved=is_saved,
        is_top=is_top,
        top_position=position,
        provider=MusicProvider.SPOTIFY,
        provider_id=spotify_artist.id,
        genres=spotify_artist.genres,
    )


def to_domain_album(spotify_album: SpotifyAlbum) -> Album:
    album_dict: dict[str, Any] = spotify_album.model_dump(by_alias=True)

    try:
        album_dict["album_type"] = AlbumType(spotify_album.album_type)
    except ValueError:
        album_dict["album_type"] = AlbumType.UNKNOWN

    return Album(**album_dict)


def to_domain_track(
    spotify_track: SpotifyTrack,
    user_id: uuid.UUID,
    is_top: bool = False,
    is_saved: bool = False,
    position: int | None = None,
) -> Track:
    """Converts a SpotifyTrack schema object to a domain Track entity."""
    return Track(
        user_id=user_id,
        name=spotify_track.name,
        popularity=spotify_track.popularity,
        is_saved=is_saved,
        is_top=is_top,
        top_position=position,
        provider=MusicProvider.SPOTIFY,
        provider_id=spotify_track.id,
        artists=[TrackArtist(provider_id=artist.id, name=artist.name) for artist in spotify_track.artists],
        album=to_domain_album(spotify_track.album) if spotify_track.album else None,
        isrc=spotify_track.isrc,
        duration_ms=spotify_track.duration_ms,
    )


def to_domain_playlist(spotify_playlist: SpotifyPlaylist, user_id: uuid.UUID, tracks: list[Track]) -> Playlist:
    return Playlist(
        user_id=user_id,
        name=spotify_playlist.name,
        provider=MusicProvider.SPOTIFY,
        provider_id=spotify_playlist.id,
        snapshot_id=spotify_playlist.snapshot_id,
        tracks=tracks,
    )
