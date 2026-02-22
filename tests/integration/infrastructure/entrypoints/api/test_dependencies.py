import logging
import uuid

from fastapi import HTTPException

import pytest

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import AccessTokenManagerPort
from spotifagent.infrastructure.config.settings.app import app_settings
from spotifagent.infrastructure.entrypoints.api.dependencies import get_current_user
from spotifagent.infrastructure.entrypoints.api.dependencies import get_user_from_state


class TestGetCurrentUser:
    async def test__nominal(
        self,
        user: User,
        user_repository: UserRepositoryPort,
        access_token_manager: AccessTokenManagerPort,
    ) -> None:
        current_user = await get_current_user(
            token=access_token_manager.create({"sub": str(user.id)}),
            user_repository=user_repository,
            access_token_manager=access_token_manager,
        )
        assert current_user.id == user.id

    async def test__error_expired_signature(
        self,
        user: User,
        user_repository: UserRepositoryPort,
        access_token_manager: AccessTokenManagerPort,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(app_settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=access_token_manager.create({"sub": str(user.id)}),
                user_repository=user_repository,
                access_token_manager=access_token_manager,
            )

        assert "Token has expired" in str(exc_info.value)

    async def test__user_not_exists(
        self,
        user_repository: UserRepositoryPort,
        access_token_manager: AccessTokenManagerPort,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG) and pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token=access_token_manager.create({"sub": str(uuid.uuid4())}),
                user_repository=user_repository,
                access_token_manager=access_token_manager,
            )

        assert exc_info is not None
        assert "Could not validate credentials" in str(exc_info.value)
        assert "No user associated to the token" in caplog.text


class TestGetUserFromState:
    async def test__nominal(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepositoryPort,
        user_repository: UserRepositoryPort,
    ) -> None:
        current_user = await get_user_from_state(
            state=auth_state.state,
            auth_state_repository=auth_state_repository,
            user_repository=user_repository,
        )

        assert current_user is not None
        assert current_user.id == user.id
