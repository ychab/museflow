import uuid

from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import TrackSource
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
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


def to_domain_track(
    spotify_track: SpotifyTrack,
    user_id: uuid.UUID,
) -> Track:
    """Converts a SpotifyTrack schema object to a domain Track entity."""
    return Track(
        user_id=user_id,
        name=spotify_track.name,
        provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id=spotify_track.id)],
        artists=[artist.name for artist in spotify_track.artists],
        album_name=spotify_track.album.name if spotify_track.album else None,
        source=TrackSource.HISTORY,
    )


def to_domain_playlist(
    spotify_playlist: SpotifyPlaylist,
    user_id: uuid.UUID,
    type: PlaylistType,
    tracks: list[Track],
) -> Playlist:
    return Playlist(
        user_id=user_id,
        name=spotify_playlist.name,
        provider=MusicProvider.SPOTIFY,
        provider_id=spotify_playlist.id,
        snapshot_id=spotify_playlist.snapshot_id,
        tracks=tracks,
        type=type,
    )
