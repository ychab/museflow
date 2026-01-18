from pydantic import ValidationError

import pytest

from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate


class TestUser:
    @pytest.mark.parametrize("user", [{"with_spotify_account": True}], indirect=True)
    def test__spotify_token_state__nominal(self, user: User) -> None:
        assert user.spotify_account is not None

        token_state = user.spotify_token_state
        assert token_state.token_type == user.spotify_account.token_type
        assert token_state.access_token == user.spotify_account.token_access
        assert token_state.refresh_token == user.spotify_account.token_refresh
        assert token_state.expires_at == user.spotify_account.token_expires_at

    @pytest.mark.parametrize("user", [{"with_spotify_account": False}], indirect=True)
    def test__spotify_token_state__exception(self, user: User) -> None:
        with pytest.raises(ValueError, match="User has no Spotify account linked"):
            user.spotify_token_state  # noqa: B018


class TestUserCreate:
    @pytest.mark.parametrize(
        ("length", "error_msg"),
        [
            (6, "String should have at least 8 characters"),
            (110, "String should have at most 100 characters"),
        ],
    )
    def test_password__length(self, length: int, error_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="foo@example.com", password="".join("a" for _ in range(0, length)))
        assert "1 validation error for UserCreate\npassword" in str(exc_info.value)
        assert error_msg in str(exc_info.value)


class TestUserUpdate:
    @pytest.mark.parametrize(
        ("length", "error_msg"),
        [
            (6, "String should have at least 8 characters"),
            (110, "String should have at most 100 characters"),
        ],
    )
    def test_password__length(self, length: int, error_msg: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(email="foo@example.com", password="".join("a" for _ in range(0, length)))
        assert "1 validation error for UserUpdate\npassword" in str(exc_info.value)
        assert error_msg in str(exc_info.value)

    def test_model_validator__one_value_set__valid(self) -> None:
        compare_page_update = UserUpdate(spotify_state=None)
        assert compare_page_update.spotify_state is None

    def test_model_validator__one_value_set__exception(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate()

        assert "1 validation error for UserUpdate" in str(exc_info.value)
        assert "At least one field must be provided for update" in str(exc_info.value)

    @pytest.mark.parametrize("field", ["email", "password"])
    def test_model_validator__cannot_be_none(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(**{field: None})

        assert "1 validation error for UserUpdate" in str(exc_info.value)
        assert f"The field '{field}' cannot be set to None" in str(exc_info.value)
