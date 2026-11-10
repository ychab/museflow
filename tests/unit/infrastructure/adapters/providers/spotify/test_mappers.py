import uuid

import pytest

from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_token_payload
from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_track
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyToken
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyTrack


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


class TestToDomainTrack:
    @pytest.mark.parametrize(
        ("album", "expected"),
        [
            pytest.param({"name": "An Album", "release_date": "1992-03-03"}, 1992, id="day"),
            pytest.param({"name": "An Album", "release_date": "1988"}, 1988, id="year"),
            pytest.param({"name": "An Album", "release_date": "0000"}, None, id="unknown"),
            pytest.param({"name": "An Album"}, None, id="missing"),
            pytest.param(None, None, id="no_album"),
        ],
    )
    def test__album_year(self, album: dict[str, str] | None, expected: int | None) -> None:
        spotify_track = SpotifyTrack.model_validate(
            {
                "id": "30xocklvViCtxktihAEZM8",
                "name": "A Song",
                "href": "https://api.spotify.com/v1/tracks/30xocklvViCtxktihAEZM8",
                "is_local": False,
                "artists": [{"name": "A Band"}],
                "album": album,
            }
        )

        assert to_domain_track(spotify_track, user_id=uuid.uuid4()).album_year == expected
