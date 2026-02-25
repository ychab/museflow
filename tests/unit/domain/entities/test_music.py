from typing import Any

from pydantic import ValidationError

import pytest

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.entities.users import User


class TestArtist:
    def test__slug__computed(self, user: User) -> None:
        artist = Artist(
            user_id=user.id,
            name="Yé hô",
            provider_id="foo",
            genres=["Pop"],
        )
        assert artist.slug == "ye-ho"

    @pytest.mark.parametrize("position", [None, 10])
    def test__position__nominal(self, user: User, position: Any) -> None:
        artist = Artist(
            user_id=user.id,
            name="Yé hô",
            provider_id="foo",
            genres=["Pop"],
            top_position=position,
        )
        assert artist.top_position == position

    @pytest.mark.parametrize(
        ("position", "expected_msg"),
        [(0, "Input should be greater than 0")],
    )
    def test__position__validation_error(self, user: User, position: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Artist(
                user_id=user.id,
                name="Yé hô",
                provider_id="foo",
                genres=["Pop"],
                top_position=position,
            )
        assert "1 validation error for Artist\ntop_position" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)

    @pytest.mark.parametrize("popularity", [None, 1, 100])
    def test__popularity__nominal(self, user: User, popularity: Any) -> None:
        artist = Artist(
            user_id=user.id,
            name="Yé hô",
            provider_id="foo",
            genres=["Pop"],
            popularity=popularity,
        )
        assert artist.popularity == popularity

    @pytest.mark.parametrize(
        ("popularity", "expected_msg"),
        [
            (-1, "Input should be greater than or equal to 0"),
            (101, "Input should be less than or equal to 100"),
        ],
    )
    def test__popularity__validation_error(self, user: User, popularity: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Artist(
                user_id=user.id,
                name="Yé hô",
                provider_id="foo",
                genres=["Pop"],
                popularity=popularity,
            )
        assert "1 validation error for Artist\npopularity" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)


class TestTrack:
    def test__slug__computed(self, user: User) -> None:
        track = Track(
            user_id=user.id,
            name="Yé hô",
            provider_id="foo",
            artists=[TrackArtist(provider_id="foo", name="foo")],
        )
        assert track.slug == "ye-ho"

    @pytest.mark.parametrize("position", [None, 10])
    def test__position__nominal(self, user: User, position: Any) -> None:
        track = Track(
            user_id=user.id,
            name="foo",
            provider_id="foo",
            artists=[TrackArtist(provider_id="foo", name="foo")],
            top_position=position,
        )
        assert track.top_position == position

    @pytest.mark.parametrize(
        ("position", "expected_msg"),
        [(0, "Input should be greater than 0")],
    )
    def test__position__validation_error(self, user: User, position: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Track(
                user_id=user.id,
                name="foo",
                provider_id="foo",
                artists=[TrackArtist(provider_id="foo", name="foo")],
                top_position=position,
            )
        assert "1 validation error for Track\ntop_position" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)

    @pytest.mark.parametrize("popularity", [None, 1, 100])
    def test__popularity__nominal(self, user: User, popularity: Any) -> None:
        track = Track(
            user_id=user.id,
            name="foo",
            provider_id="foo",
            artists=[TrackArtist(provider_id="foo", name="foo")],
            popularity=popularity,
        )
        assert track.popularity == popularity

    @pytest.mark.parametrize(
        ("popularity", "expected_msg"),
        [
            (-1, "Input should be greater than or equal to 0"),
            (101, "Input should be less than or equal to 100"),
        ],
    )
    def test__popularity__validation_error(self, user: User, popularity: Any, expected_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Track(
                user_id=user.id,
                name="foo",
                provider_id="foo",
                artists=[TrackArtist(provider_id="foo", name="foo")],
                popularity=popularity,
            )
        assert "1 validation error for Track\npopularity" in str(exc_info.value)
        assert expected_msg in str(exc_info.value)
