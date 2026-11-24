import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.user_get import get_user
from museflow.application.use_cases.user_get import get_user_by_id
from museflow.domain.exceptions import UserNotFoundError


class TestGetUserUseCase:
    async def test__not_found(self, mock_uow: mock.AsyncMock, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError, match="User with email 'ghost@example.com' not found."):
            await get_user(email="ghost@example.com", uow=mock_uow)


class TestGetUserByIdUseCase:
    async def test__not_found(self, mock_uow: mock.AsyncMock, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_id.return_value = None
        user_id = uuid.uuid4()

        with pytest.raises(UserNotFoundError, match=f"User {user_id} not found."):
            await get_user_by_id(user_id, uow=mock_uow)
