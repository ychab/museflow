import logging
import uuid
from unittest import mock

from fastapi import HTTPException

import pytest
from jwt import InvalidTokenError

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.users import User
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_user_from_state


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


class TestGetUserFromState:
    async def test__state__missing(
        self,
        mock_auth_state_repository: mock.AsyncMock,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        with pytest.raises(HTTPException, match="Missing state parameter"):
            await get_user_from_state(
                state="",
                auth_state_repository=mock_auth_state_repository,
                user_repository=mock_user_repository,
            )

    async def test__state__invalid(
        self,
        mock_auth_state_repository: mock.AsyncMock,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = None

        with pytest.raises(HTTPException, match="Invalid or expired state"):
            await get_user_from_state(
                state="dummy-state",
                auth_state_repository=mock_auth_state_repository,
                user_repository=mock_user_repository,
            )

    @pytest.mark.parametrize("auth_state", [{"user_id": uuid.uuid4()}], indirect=True)
    async def test__user__unknown(
        self,
        auth_state: OAuthProviderState,
        mock_auth_state_repository: mock.AsyncMock,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_state_repository.consume.return_value = auth_state
        mock_user_repository.get_by_id.return_value = None

        with pytest.raises(HTTPException, match="Unable to load user from state"):
            await get_user_from_state(
                state=auth_state.state,
                auth_state_repository=mock_auth_state_repository,
                user_repository=mock_user_repository,
            )
