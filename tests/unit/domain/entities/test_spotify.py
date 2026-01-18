from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

import pytest

from spotifagent.domain.entities.spotify import SpotifyAccountUpdate
from spotifagent.domain.entities.spotify import SpotifyScope
from spotifagent.domain.entities.spotify import SpotifyTokenState


class TestSpotifyScope:
    def test_all(self) -> None:
        assert len(SpotifyScope.all()) == len(SpotifyScope)

    def test_to_scope_string(self) -> None:
        scope_str = SpotifyScope.to_scope_string(
            [
                SpotifyScope.USER_READ_EMAIL,
                SpotifyScope.USER_READ_PRIVATE,
            ]
        )
        assert scope_str == "user-read-email user-read-private"


class TestSpotifyTokenState:
    @pytest.mark.parametrize(
        ("token_state", "expected_bool"),
        [
            ({"expires_at": datetime(2026, 1, 1, 0, 1, 10, tzinfo=UTC)}, False),
            ({"expires_at": datetime(2026, 1, 1, 0, 0, 50, tzinfo=UTC)}, True),
        ],
        indirect=["token_state"],
    )
    def test__is_expired(self, frozen_time: datetime, token_state: SpotifyTokenState, expected_bool: bool) -> None:
        assert token_state.is_expired(60) is expected_bool

    @pytest.mark.parametrize("expires_at", [datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)])
    def test_calculate_expires_at__with_expires_at(self, expires_at: datetime) -> None:
        token_state = SpotifyTokenState(
            token_type="bearer",
            access_token="dummy-access-token",
            refresh_token="dummy-refresh-token",
            expires_at=expires_at,
        )
        assert token_state.expires_at == expires_at

    def test_calculate_expires_at__with_expires_in(self, frozen_time: datetime) -> None:
        expires_in = 3600
        token_state = SpotifyTokenState(
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
            SpotifyTokenState(**payload)


class TestSpotifyAccountUpdate:
    def test_validate_one_field_set__nominal(self) -> None:
        spotify_account_update = SpotifyAccountUpdate(token_type="bearer")
        assert spotify_account_update.token_type == "bearer"

    def test_validate_one_field_set__error(self) -> None:
        with pytest.raises(ValueError, match="At least one field must be provided for update"):
            SpotifyAccountUpdate()
