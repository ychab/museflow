from unittest import mock

import pytest

from museflow.application.use_cases.user_authenticate import user_authenticate
from museflow.domain.entities.users import User
from museflow.domain.exceptions import UserInactive
from museflow.domain.exceptions import UserInvalidCredentials
from museflow.domain.exceptions import UserNotFound


class TestUserService:
    async def test_authenticate__nominal(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user

        user_auth = await user_authenticate(
            email=user.email,
            password="testtest",
            user_repository=mock_user_repository,
            password_hasher=mock_password_hasher,
        )
        assert user_auth is not None
        assert user_auth.email == user.email

    async def test_authenticate__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await user_authenticate(
                email="foo@example.com",
                password="testtest",
                user_repository=mock_user_repository,
                password_hasher=mock_password_hasher,
            )

    async def test_authenticate__wrong_password(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_password_hasher.verify.return_value = False

        with pytest.raises(UserInvalidCredentials):
            await user_authenticate(
                email=user.email,
                password="blahblah",
                user_repository=mock_user_repository,
                password_hasher=mock_password_hasher,
            )

    @pytest.mark.parametrize("user", [{"is_active": False}], indirect=True)
    async def test_authenticate__inactive(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_password_hasher: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user

        with pytest.raises(UserInactive):
            await user_authenticate(
                email=user.email,
                password="testtest",
                user_repository=mock_user_repository,
                password_hasher=mock_password_hasher,
            )
