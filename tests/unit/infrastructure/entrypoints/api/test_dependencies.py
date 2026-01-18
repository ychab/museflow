import logging
from unittest import mock

from fastapi import HTTPException

import pytest
from jwt import InvalidTokenError

from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.entrypoints.api.dependencies import get_current_user
from spotifagent.infrastructure.entrypoints.api.dependencies import get_user_from_spotify_state


class TestGetCurrentUser:
    async def test__nominal(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
    ) -> None:
        mock_user_repository.get_by_id.return_value = user
        mock_access_token_manager.decode.return_value = {"sub": str(user.id)}

        current_user = await get_current_user(
            token="dummy-access-token",
            user_repository=mock_user_repository,
            access_token_manager=mock_access_token_manager,
        )
        assert current_user.id == user.id

    async def test__no_user_id(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_access_token_manager.decode.return_value = {}

        with caplog.at_level(logging.DEBUG) and pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="dummy-access-token",
                user_repository=mock_user_repository,
                access_token_manager=mock_access_token_manager,
            )

        assert exc_info is not None
        assert "Could not validate credentials" in str(exc_info.value)
        assert "No user ID found in token" in caplog.text

    async def test__error__invalid_token(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_access_token_manager.decode.side_effect = InvalidTokenError()

        with caplog.at_level(logging.DEBUG) and pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="dummy-access-token",
                user_repository=mock_user_repository,
                access_token_manager=mock_access_token_manager,
            )

        assert exc_info is not None
        assert "Could not validate credentials" in str(exc_info.value)
        assert "Invalid token" in caplog.text


class TestGetUserFromSpotifyState:
    @pytest.mark.parametrize("user", [{"spotify_state": "dummy-token-state"}], indirect=["user"])
    async def test__nominal(self, user: User, mock_user_repository: mock.AsyncMock) -> None:
        assert user.spotify_state is not None
        mock_user_repository.get_by_spotify_state.return_value = user

        current_user = await get_user_from_spotify_state(
            state=user.spotify_state, user_repository=mock_user_repository
        )
        assert current_user is not None
        assert current_user.id == user.id

    async def test__missing_state(self) -> None:
        with pytest.raises(HTTPException, match="Missing state parameter"):
            await get_user_from_spotify_state(state="", user_repository=mock.Mock())

    async def test__missing_user(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_spotify_state.return_value = None

        with pytest.raises(HTTPException, match="Invalid or expired state"):
            await get_user_from_spotify_state(state="fake-token", user_repository=mock_user_repository)
