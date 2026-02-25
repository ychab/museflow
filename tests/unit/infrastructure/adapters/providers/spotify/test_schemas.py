from datetime import datetime
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyScope
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyToken


class TestSpotifyScope:
    def test_required_scopes(self) -> None:
        assert SpotifyScope.required_scopes() == "user-top-read user-library-read playlist-read-private"


class TestSpotifyToken:
    def test_expires_in__invalid(self, frozen_time: datetime) -> None:
        payload: dict[str, Any] = {
            "token_type": "bearer",
            "access_token": "dummy-access-token",
            "refresh_token": "dummy-refresh-token",
            "expires_in": -15,
        }

        with pytest.raises(ValidationError) as exc_info:
            SpotifyToken(**payload)

        assert "1 validation error for SpotifyToken" in str(exc_info.value)
        assert "expires_in\n  Input should be greater than or equal to 0" in str(exc_info.value)

    def test_expires_at__nominal(self, frozen_time: datetime) -> None:
        expires_in = 3600
        token_state = SpotifyToken(
            **{
                "token_type": "bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_in": expires_in,
            }
        )
        assert token_state.expires_at == frozen_time + timedelta(seconds=expires_in)

    def test_to_domain__missing_refresh_token(self) -> None:
        payload: dict[str, Any] = {
            "token_type": "bearer",
            "access_token": "dummy-access-token",
            "expires_in": 15,
        }

        with pytest.raises(ValueError, match="Refresh token is missing from both response and existing state."):
            SpotifyToken(**payload).to_domain()
