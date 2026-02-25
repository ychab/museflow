from collections.abc import AsyncGenerator
from collections.abc import Iterator
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock

from httpx import ASGITransport
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.domain.entities.users import User
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.security import AccessTokenManagerPort
from museflow.infrastructure.entrypoints.api.dependencies import get_access_token_manager
from museflow.infrastructure.entrypoints.api.dependencies import get_db
from museflow.infrastructure.entrypoints.api.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.api.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.users import UserModelFactory


@pytest.fixture(name="mock_api_logger")
def block_api_logging_reconfiguration() -> Iterator[mock.Mock]:
    """Prevents FastAPI lifespan from overwriting test logging config."""
    with mock.patch("museflow.infrastructure.entrypoints.api.main.configure_loggers") as patched:
        yield patched


@pytest.fixture
async def mock_db_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
async def mock_spotify_client() -> AsyncMock:
    return AsyncMock(spec=ProviderOAuthClientPort)


@pytest.fixture
async def user(request: pytest.FixtureRequest) -> User:
    params: dict[str, Any] = getattr(request, "param", {})
    user_db = await UserModelFactory.create_async(**params)
    return User.model_validate(user_db)


@pytest.fixture
def access_token(access_token_manager: AccessTokenManagerPort, user: User) -> str:
    return access_token_manager.create({"sub": str(user.id)})


@pytest.fixture
async def async_client(
    mock_api_logger: None,
    async_session_db: AsyncSession,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[AsyncClient]:
    """
    AsyncClient with optional authentication.

    IMPORTANT: Place fixtures dependencies first:
        async def test_XXX(user, access_token, mock_spotify_client, async_client):
    NOT: async_client BEFORE:
        async def test_XXX(async_client, user, access_token, mock_spotify_client):

    Usage:
        # Anonymous
        async def test_public(async_client): ...

        # Authenticated (note the order!)
        async def test_protected(access_token, async_client): ...

        # Authenticated with spotify_mock (note the order!)
        async def test_protected(access_token, mock_spotify_client, async_client): ...

        etc.
    """

    # Override get_db: use mock_db if present, otherwise use test session
    if "mock_db_session" in request.fixturenames:
        mock_db_session = request.getfixturevalue("mock_db_session")

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
    else:

        async def override_get_db():
            yield async_session_db

        app.dependency_overrides[get_db] = override_get_db

    # Override Spotify client if fixture is used
    if "mock_spotify_client" in request.fixturenames:
        mock_client = request.getfixturevalue("mock_spotify_client")
        app.dependency_overrides[get_spotify_client] = lambda: mock_client

    # Override security password hasher ports
    if "password_hasher" in request.fixturenames:
        password_hasher_fixture = request.getfixturevalue("password_hasher")
        app.dependency_overrides[get_password_hasher] = lambda: password_hasher_fixture

    # Override security access token manager ports
    if "access_token_manager" in request.fixturenames:
        access_token_manager_fixture = request.getfixturevalue("access_token_manager")
        app.dependency_overrides[get_access_token_manager] = lambda: access_token_manager_fixture

    # Check if access_token fixture is available in test
    headers: dict[str, str] = {}
    if "access_token" in request.fixturenames:
        access_token = request.getfixturevalue("access_token")
        headers["Authorization"] = f"Bearer {access_token}"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    ) as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()
