from unittest import mock

import pytest

from museflow.application.inputs.user import UserCreateInput
from museflow.application.use_cases.user_create import user_create
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsException

from tests.unit.factories.inputs.user import UserCreateInputFactory


class TestUserCreateUseCase:
    @pytest.fixture
    def user_create_data(self) -> UserCreateInput:
        return UserCreateInputFactory.build(password="testtest")

    async def test_create_user__already_exists(
        self,
        user: User,
        user_create_data: UserCreateInput,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user

        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await user_create(user_create_data, mock_user_repository, mock_password_hasher)
        assert "Email already registered" in str(exc_info.value)
