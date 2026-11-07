from unittest import mock

import pytest

from museflow.application.use_cases.user_authenticate import authenticate_user
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserInactiveError
from museflow.domain.exceptions import UserInvalidCredentialsError
from museflow.domain.exceptions import UserNotFoundError


class TestAuthenticateUserUseCase:
    async def test__authenticate__not_found(
        self,
        mock_uow: mock.AsyncMock,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await authenticate_user(
                email="foo@example.com",
                password="testtest",
                uow=mock_uow,
                password_hasher=mock_password_hasher,
            )

        mock_password_hasher.verify_simulate.assert_called_once_with("testtest")

    async def test__authenticate__wrong_password(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_password_hasher.verify.return_value = False

        with pytest.raises(UserInvalidCredentialsError):
            await authenticate_user(
                email=user.email,
                password="blahblah",
                uow=mock_uow,
                password_hasher=mock_password_hasher,
            )

    @pytest.mark.parametrize("user", [{"is_active": False}], indirect=True)
    async def test__authenticate__inactive(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user

        with pytest.raises(UserInactiveError):
            await authenticate_user(
                email=user.email,
                password="testtest",
                uow=mock_uow,
                password_hasher=mock_password_hasher,
            )
