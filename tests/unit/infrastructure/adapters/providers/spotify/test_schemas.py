from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

import pytest

from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyScope
from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyTokenStateDTO


class TestSpotifyScope:
    def test_required_scopes(self) -> None:
        assert SpotifyScope.required_scopes() == "user-top-read user-library-read playlist-read-private"


class TestSpotifyTokenStateDTO:
    @pytest.mark.parametrize("expires_at", [datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)])
    def test_calculate_expires_at__with_expires_at(self, expires_at: datetime) -> None:
        token_state = SpotifyTokenStateDTO(
            token_type="bearer",
            access_token="dummy-access-token",
            refresh_token="dummy-refresh-token",
            expires_at=expires_at,
        )
        assert token_state.expires_at == expires_at

    def test_calculate_expires_at__with_expires_in(self, frozen_time: datetime) -> None:
        expires_in = 3600
        token_state = SpotifyTokenStateDTO(
            **{
                "token_type": "bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_in": expires_in,
            }
        )
        assert token_state.expires_at == frozen_time + timedelta(seconds=expires_in)

    @pytest.mark.parametrize("payload_extra", [{}, {"expires_in": "foo"}, {"expires_in": -15}])
    def test_calculate_expires_at__errors(self, payload_extra: Any) -> None:
        payload: dict[str, Any] = {
            "access_token": "dummy-access-token",
            "refresh_token": "dummy-refresh-token",
            **payload_extra,
        }

        with pytest.raises(ValidationError, match="Input must contain a positive integer 'expires_in' or 'expires_at"):
            SpotifyTokenStateDTO(**payload)
