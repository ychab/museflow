import pytest

from museflow.domain.types import AlbumType
from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_album
from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_token_payload
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyAlbum
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyToken


class TestToDomainTokenPayload:
    def test__missing_refresh_token(self) -> None:
        spotify_token = SpotifyToken(
            token_type="bearer",
            access_token="dummy-access-token",
            refresh_token=None,
            expires_in=15,
        )

        with pytest.raises(ValueError, match="Refresh token is missing from both response and existing state."):
            to_domain_token_payload(spotify_token)


class TestToDomainAlbum:
    def test__nominal(self) -> None:
        spotify_album = SpotifyAlbum(
            id="dummy-id",
            name="foo",
            album_type="album",
        )

        album = to_domain_album(spotify_album)

        assert album.provider_id == "dummy-id"
        assert album.name == "foo"
        assert album.album_type == AlbumType.ALBUM

    def test__unknown(self) -> None:
        spotify_album = SpotifyAlbum(
            id="dummy-id",
            name="foo",
            album_type="a-super-weird-album-type",
        )

        album = to_domain_album(spotify_album)

        assert album.album_type == AlbumType.UNKNOWN
