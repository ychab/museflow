import pytest

from museflow.infrastructure.adapters.providers.spotify.mappers import to_domain_token_payload
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
