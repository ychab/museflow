from datetime import datetime
from datetime import timedelta
from typing import Any

from pydantic import HttpUrl
from pydantic import ValidationError

import pytest

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyArtist
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyToken
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyTrack
from museflow.infrastructure.adapters.providers.spotify.schemas import SpotifyTrackArtist
from museflow.infrastructure.adapters.providers.spotify.types import SpotifyScope


class TestSpotifyScope:
    def test_required_scopes(self) -> None:
        assert SpotifyScope.required_scopes() == "user-top-read user-library-read playlist-read-private"


class TestSpotifyArtist:
    def test__id__validation_error(self, user: User) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyArtist(
                id="".join(["a" for _ in range(513)]),
                name="Yé hô",
                href=HttpUrl("https://spotify.com/foo"),
                popularity=50,
                genres=["Pop"],
            )
        assert "1 validation error for SpotifyArtist\nid" in str(exc_info.value)
        assert "String should have at most 512 characters" in str(exc_info.value)

    def test__name__validation_error(self, user: User) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyArtist(
                id="foo",
                name="".join(["a" for _ in range(256)]),
                href=HttpUrl("https://spotify.com/foo"),
                popularity=50,
                genres=["Pop"],
            )
        assert "1 validation error for SpotifyArtist\nname" in str(exc_info.value)
        assert "String should have at most 255 characters" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("popularity", "expected_msg"),
        [
            (-1, "Input should be greater than or equal to 0"),
            (101, "Input should be less than or equal to 100"),
        ],
    )
    def test__popularity__validation_error(self, user: User, popularity: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyArtist(
                id="foo",
                name="Yé hô",
                href=HttpUrl("https://spotify.com/foo"),
                popularity=popularity,
                genres=["Pop"],
            )
        assert "1 validation error for SpotifyArtist\npopularity" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)


class TestSpotifyTrack:
    def test__id__validation_error(self, user: User) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyTrack(
                id="".join(["a" for _ in range(513)]),
                name="Yé hô",
                href=HttpUrl("https://spotify.com/foo"),
                popularity=50,
                artists=[SpotifyTrackArtist(id="foo", name="foo")],
            )
        assert "1 validation error for SpotifyTrack\nid" in str(exc_info.value)
        assert "String should have at most 512 characters" in str(exc_info.value)

    def test__name__validation_error(self, user: User) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyTrack(
                id="foo",
                name="".join(["a" for _ in range(256)]),
                href=HttpUrl("https://spotify.com/foo"),
                popularity=50,
                artists=[SpotifyTrackArtist(id="foo", name="foo")],
            )
        assert "1 validation error for SpotifyTrack\nname" in str(exc_info.value)
        assert "String should have at most 255 characters" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("popularity", "expected_msg"),
        [
            (-1, "Input should be greater than or equal to 0"),
            (101, "Input should be less than or equal to 100"),
        ],
    )
    def test__popularity__validation_error(self, user: User, popularity: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SpotifyTrack(
                id="foo",
                name="Yé hô",
                href=HttpUrl("https://spotify.com/foo"),
                popularity=popularity,
                artists=[SpotifyTrackArtist(id="foo", name="foo")],
            )
        assert "1 validation error for SpotifyTrack\npopularity" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)


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
        spotify_token = SpotifyToken(
            **{
                "token_type": "bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_in": expires_in,
            }
        )
        assert spotify_token.expires_at == frozen_time + timedelta(seconds=expires_in)
