import logging
from unittest import mock

from fastapi import HTTPException

from pydantic import AnyUrl

from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest
from jwt import InvalidTokenError

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_redirect_uri
from museflow.infrastructure.entrypoints.api.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.api.dependencies import get_wiring
from museflow.infrastructure.entrypoints.wiring import Wiring


class TestGetWiring:
    def test__opened_by_the_lifespan(self) -> None:
        request = mock.Mock()
        assert get_wiring(request) is request.app.state.wiring


class TestGetUnitOfWork:
    def test__new_instance_per_call(self) -> None:
        # FastAPI caches it per request only: two requests never share a unit of work.
        wiring = Wiring(mock.Mock(spec=async_sessionmaker))
        uow = get_unit_of_work(wiring)
        assert isinstance(uow, SQLUnitOfWork)
        assert get_unit_of_work(wiring) is not uow


class TestGetCurrentUser:
    async def test__nominal(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
    ) -> None:
        mock_user_repository.get_by_id.return_value = user
        mock_access_token_manager.decode.return_value = {"sub": str(user.id)}

        current_user = await get_current_user(
            token="dummy-access-token",
            uow=mock_uow,
            access_token_manager=mock_access_token_manager,
        )
        assert current_user.id == user.id

    async def test__no_user_id(
        self,
        mock_uow: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_access_token_manager.decode.return_value = {}

        with caplog.at_level(logging.DEBUG) and pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="dummy-access-token",
                uow=mock_uow,
                access_token_manager=mock_access_token_manager,
            )

        assert exc_info is not None
        assert "Could not validate credentials" in str(exc_info.value)
        assert "No user ID found in token" in caplog.text

    async def test__error__invalid_token(
        self,
        mock_uow: mock.AsyncMock,
        mock_access_token_manager: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_access_token_manager.decode.side_effect = InvalidTokenError()

        with caplog.at_level(logging.DEBUG) and pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="dummy-access-token",
                uow=mock_uow,
                access_token_manager=mock_access_token_manager,
            )

        assert exc_info is not None
        assert "Could not validate credentials" in str(exc_info.value)
        assert "Invalid token" in caplog.text


class TestGetRedirectUri:
    def test__provider__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            get_redirect_uri(
                provider="FOO",  # type: ignore[arg-type]
                redirect_uri=AnyUrl("https://app.example.com/spotify/callback"),
            )
