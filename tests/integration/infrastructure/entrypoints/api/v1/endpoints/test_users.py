from typing import Any

from httpx import AsyncClient
from starlette import status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import AccessTokenManagerPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.infrastructure.adapters.database.models import User as UserModel
from spotifagent.infrastructure.entrypoints.api.main import app

from tests.integration.factories.users import UserModelFactory


class TestUserRegister:
    async def test_nominal(
        self,
        password_hasher: PasswordHasherPort,
        access_token_manager: AccessTokenManagerPort,
        user_repository: UserRepositoryPort,
        async_client: AsyncClient,
    ) -> None:
        payload: dict[str, Any] = {
            "email": "foo@example.com",
            "password": "testtest",
        }
        url = app.url_path_for("user_register")

        response = await async_client.post(url, json=payload)
        assert response.status_code == status.HTTP_201_CREATED

        response_data = response.json()
        assert response_data["user"]["id"] is not None
        assert response_data["user"]["email"] == payload["email"]
        assert response_data["user"]["is_active"] is True
        assert response_data["token_type"] == "Bearer"
        assert response_data["access_token"] is not None

        user = await user_repository.get_by_email(payload["email"])
        assert user is not None
        assert password_hasher.verify(payload["password"], user.hashed_password) is True

        decoded_token = access_token_manager.decode(response_data["access_token"])
        assert decoded_token["sub"] == str(user.id)

    async def test_password_min_length(self, async_client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "email": "foo@example.com",
            "password": "test",
        }
        url = app.url_path_for("user_register")

        response = await async_client.post(url, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        response_data = response.json()
        assert "String should have at least 8 characters" in response_data["detail"][0]["msg"]

    async def test_user_already_exists(self, user: User, async_client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "email": user.email,
            "password": "testtest",
        }
        url = app.url_path_for("user_register")

        response = await async_client.post(url, json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert "Email already registered" in response_data["detail"]


class TestUserLogin:
    async def test_nominal(
        self,
        access_token_manager: AccessTokenManagerPort,
        async_client: AsyncClient,
        user: User,
    ) -> None:
        url = app.url_path_for("user_login")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload: dict[str, Any] = {
            "username": user.email,
            "password": "testtest",
        }

        response = await async_client.post(url, headers=headers, data=payload)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["user"]["id"] == str(user.id)
        assert response_data["user"]["email"] == str(user.email)
        assert response_data["user"]["is_active"] is True

        assert response_data["token_type"] == "Bearer"
        assert response_data["access_token"] is not None

        decoded_token = access_token_manager.decode(response_data["access_token"])
        assert decoded_token["sub"] == str(user.id)

    async def test_email_invalid(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("user_login")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload: dict[str, Any] = {
            "username": "foo@example.com",
            "password": "testtest",
        }

        response = await async_client.post(url, headers=headers, data=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response_data = response.json()
        assert "Invalid credentials" in response_data["detail"]

    async def test_password_invalid(self, async_client: AsyncClient, user: User) -> None:
        url = app.url_path_for("user_login")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload: dict[str, Any] = {
            "username": user.email,
            "password": "test",
        }

        response = await async_client.post(url, headers=headers, data=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response_data = response.json()
        assert "Invalid credentials" in response_data["detail"]

    @pytest.mark.parametrize("user", [{"is_active": False}], indirect=True)
    async def test_not_active(self, async_client: AsyncClient, user: User) -> None:
        url = app.url_path_for("user_login")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload: dict[str, Any] = {
            "username": user.email,
            "password": "testtest",
        }

        response = await async_client.post(url, headers=headers, data=payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response_data = response.json()
        assert "User account is inactive" in response_data["detail"]


class TestUserCurrentInfo:
    async def test_not_authenticated(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("user_me")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_authenticated(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("user_me")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["id"] == str(user.id)
        assert response_data["email"] == str(user.email)
        assert response_data["is_active"] is True


class TestUserCurrentUpdate:
    async def test_not_authenticated(self, async_client: AsyncClient) -> None:
        payload: dict[str, Any] = {
            "email": "bar@example.com",
            "password": "blahblah",
        }
        url = app.url_path_for("user_me")

        response = await async_client.patch(url, json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("user", [{"email": "foo@example.com"}], indirect=True)
    async def test_update__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        access_token: str,
        password_hasher: PasswordHasherPort,
        async_client: AsyncClient,
    ) -> None:
        payload: dict[str, Any] = {
            "email": "bar@example.com",
            "password": "blahblah",
        }
        url = app.url_path_for("user_me")

        response = await async_client.patch(url, json=payload)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["id"] == str(user.id)

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one()

        assert user_db.email == response_data["email"] == payload["email"]
        assert password_hasher.verify(payload["password"], user_db.hashed_password) is True

    async def test_update_email__already_exists(
        self,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        user_other = await UserModelFactory.create_async()
        payload: dict[str, Any] = {
            "email": str(user_other.email),
        }
        url = app.url_path_for("user_me")

        response = await async_client.patch(url, json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Email already registered"


class TestUserCurrentDelete:
    async def test_not_authenticated(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("user_me")
        response = await async_client.delete(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_delete(
        self,
        async_session_db: AsyncSession,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("user_me")
        response = await async_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one_or_none()
        assert user_db is None
