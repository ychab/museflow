import os
import re
from collections.abc import AsyncGenerator
from collections.abc import Iterable

from pydantic import HttpUrl

from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

import pytest
from tenacity import stop_after_attempt

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput
from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.users import UserRepository
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import MusicProvider
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.advisors.http import HttpAdvisorMixin
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmClientAdapter
from museflow.infrastructure.adapters.database.models import Base
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderStateSQLRepository
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import ArtistSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import TrackSQLRepository
from museflow.infrastructure.adapters.database.repositories.users import UserSQLRepository
from museflow.infrastructure.adapters.database.session import async_session_factory
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyClientAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import JwtAccessTokenManager
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.database import database_settings

from tests.integration.factories.models.auth import AuthProviderStateModelFactory
from tests.integration.factories.models.auth import AuthProviderTokenFactory
from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.integration.utils.wiremock import WireMockContext
from tests.unit.factories.inputs.auth import OAuthProviderUserTokenCreateInputFactory
from tests.unit.factories.inputs.auth import OAuthProviderUserTokenUpdateInputFactory
from tests.unit.factories.inputs.user import UserCreateInputFactory
from tests.unit.factories.inputs.user import UserUpdateInputFactory
from tests.unit.factories.value_objects.auth import OAuthProviderTokenPayloadFactory


@pytest.fixture(scope="session")
def test_db_name(worker_id: str) -> str:
    if database_settings.URI is None or not database_settings.URI.path:
        pytest.exit("Missing DATABASE_URI env var (or composites)", 1)

    basename = re.sub(r"[^a-z0-9_]", "_", database_settings.URI.path[1:])
    return f"test_{basename}" if worker_id == "master" else f"test_{basename}_{worker_id}"


@pytest.fixture(scope="session")
async def create_test_database(anyio_backend: str, test_db_name: str) -> AsyncGenerator[None]:
    """
    Creates a dedicated test database at the start of the session and drops it at the end.

    This fixture operates in AUTOCOMMIT mode to allow CREATE/DROP DATABASE commands.
    It ensures tests run in a clean, isolated environment separate from development/production DBs.
    """

    # Establish a connection to the current DB with admin role.
    async_engine_admin: AsyncEngine = create_async_engine(
        url=str(database_settings.URI),
        isolation_level="AUTOCOMMIT",
    )
    # Then drop/create test database
    async with async_engine_admin.connect() as async_conn:
        await async_conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        await async_conn.execute(text(f"CREATE DATABASE {test_db_name}"))

    yield

    # Finally drop the test database
    async with async_engine_admin.connect() as async_conn:
        await async_conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    await async_engine_admin.dispose()


@pytest.fixture(scope="session")
async def async_engine(create_test_database: None, test_db_name: str) -> AsyncGenerator[AsyncEngine]:
    url = make_url(str(database_settings.URI)).set(database=test_db_name)
    async_engine = create_async_engine(url=url)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_engine

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await async_engine.dispose()


@pytest.fixture(scope="function")
async def async_session_trans(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """
    Provides an async session for tests requiring explicit transaction commits.

    Use this fixture ONLY when testing logic that calls `session.commit()` directly
    (e.g., Use Cases that must persist data).

    Behavior:
        - Yields a session.
        - Commits data to the DB.
        - Cleans up via TRUNCATE after the test (slower than rollback).
    """
    async_session_factory.configure(bind=async_engine)

    async with async_session_factory() as async_session_db:
        # Attach active session on DB factories first.
        BaseModelFactory.__async_session__ = async_session_db

        # Then yield the DB connection.
        yield async_session_db

        # Cleanup after test
        await async_session_db.close()

        # Truncate all tables
        async with async_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="function", autouse=True)
async def async_session_db(
    async_engine: AsyncEngine,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[AsyncSession | None]:
    """
    Provides the default async session wrapped in a transaction that rolls back.

    This is the standard fixture for 99% of tests. It allows code to "commit" (flush),
    but ultimately rolls back the entire transaction at the end of the test function.

    Behavior:
        - Faster than `async_session_trans` (no disk writes/truncate).
        - Monkeypatches `session.commit` to `session.flush`.
    """
    # Check if the conflicting fixture is requested for this test
    if "async_session_trans" in request.fixturenames:
        yield None
        return

    async with async_engine.connect() as conn:
        # Begin a non-ORM transaction
        transaction = await conn.begin()

        # Create a session explicitly bound to this connection
        async with async_session_factory(bind=conn) as async_session:
            # Inject session into Polyfactory
            BaseModelFactory.__async_session__ = async_session

            # Monkeypatch commit to flush.
            # This ensures that when the API or CLI calls 'await session.commit()',
            # it only sends the SQL (flush) but DOES NOT close the transaction.
            # The data is visible to subsequent selects in the test, but
            # allows the rollback below to still work.
            async_session.commit = async_session.flush

            yield async_session

        # Rollback the transaction
        await transaction.rollback()


# --- Security impl ---


@pytest.fixture
def password_hasher() -> PasswordHasherPort:
    return get_password_hasher()


@pytest.fixture
def access_token_manager() -> AccessTokenManagerPort:
    return get_access_token_manager()


@pytest.fixture
def state_token_generator() -> StateTokenGeneratorPort:
    return get_state_token_generator()


# --- Repository impl ---


@pytest.fixture
def user_repository(async_session_db: AsyncSession) -> UserRepository:
    return UserSQLRepository(async_session_db)


@pytest.fixture
def auth_state_repository(async_session_db: AsyncSession) -> OAuthProviderStateRepository:
    return OAuthProviderStateSQLRepository(async_session_db)


@pytest.fixture
def auth_token_repository(async_session_db: AsyncSession) -> OAuthProviderTokenRepository:
    return OAuthProviderTokenSQLRepository(async_session_db)


@pytest.fixture
def artist_repository(async_session_db: AsyncSession) -> ArtistRepository:
    return ArtistSQLRepository(async_session_db)


@pytest.fixture
def track_repository(async_session_db: AsyncSession) -> TrackRepository:
    return TrackSQLRepository(async_session_db)


# --- Entity factories ---


@pytest.fixture
def user_create(request: pytest.FixtureRequest) -> UserCreateInput:
    return UserCreateInputFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def user_update(request: pytest.FixtureRequest) -> UserUpdateInput:
    return UserUpdateInputFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def token_payload(request: pytest.FixtureRequest) -> OAuthProviderTokenPayload:
    return OAuthProviderTokenPayloadFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def auth_token_create() -> OAuthProviderUserTokenCreateInput:
    return OAuthProviderUserTokenCreateInputFactory.build()


@pytest.fixture
def auth_token_update() -> OAuthProviderUserTokenUpdateInput:
    return OAuthProviderUserTokenUpdateInputFactory.build()


# --- Models DB factories ---


@pytest.fixture
async def user(request: pytest.FixtureRequest) -> User:
    user_db = await UserModelFactory.create_async(**getattr(request, "param", {}))
    return user_db.to_entity()


@pytest.fixture
async def auth_state(request: pytest.FixtureRequest, user: User) -> OAuthProviderState:
    params = getattr(request, "param", {})
    params.setdefault("user_id", user.id)

    auth_state_db = await AuthProviderStateModelFactory.create_async(**params)
    return auth_state_db.to_entity()


@pytest.fixture
async def auth_token(request: pytest.FixtureRequest, user: User) -> OAuthProviderUserToken:
    params = getattr(request, "param", {})
    user_id = params.pop("user_id", user.id)
    provider = params.pop("provider", MusicProvider.SPOTIFY)

    auth_token_db = await AuthProviderTokenFactory.create_async(user_id=user_id, provider=provider, **params)
    return auth_token_db.to_entity()


# --- Clients impl ---


@pytest.fixture
async def spotify_client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[SpotifyClientAdapter]:
    base_url: str | None = os.getenv("WIREMOCK_SPOTIFY_BASE_URL")

    retry_method = SpotifyClientAdapter.make_api_call
    monkeypatch.setattr(retry_method.retry, "stop", stop_after_attempt(1))  # type: ignore[attr-defined]

    async with SpotifyClientAdapter(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        redirect_uri=HttpUrl("http://127.0.0.1:8000/api/v1/spotify/callback"),
        base_url=HttpUrl(base_url) if base_url else None,
        # For simplicity, we are using the same WireMock server for these two dedicated endpoints
        auth_endpoint=HttpUrl(f"{base_url}/authorize") if base_url else None,
        token_endpoint=HttpUrl(f"{base_url}/api/token") if base_url else None,
        # Don't verify the self-signed cert of WireMock
        verify_ssl=False,
    ) as client:
        yield client


@pytest.fixture
def spotify_session_client(
    user: User,
    auth_token: OAuthProviderUserToken,
    auth_token_repository: OAuthProviderTokenRepository,
    spotify_client: SpotifyClientAdapter,
) -> SpotifyOAuthSessionClient:
    return SpotifyOAuthSessionClient(
        user=user,
        auth_token=auth_token,
        auth_token_repository=auth_token_repository,
        client=spotify_client,
    )


@pytest.fixture
def spotify_library(
    request: pytest.FixtureRequest,
    user: User,
    spotify_session_client: SpotifyOAuthSessionClient,
) -> SpotifyLibraryAdapter:
    params = getattr(request, "param", {})
    max_concurrency = params.get("max_concurrency", 20)

    return SpotifyLibraryAdapter(
        user=user,
        session_client=spotify_session_client,
        max_concurrency=max_concurrency,
    )


@pytest.fixture
async def lastfm_client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[LastFmClientAdapter]:
    base_url: str | None = os.getenv("WIREMOCK_LASTFM_BASE_URL")

    retry_method = HttpAdvisorMixin.make_api_call
    monkeypatch.setattr(retry_method.retry, "stop", stop_after_attempt(1))  # type: ignore[attr-defined]

    async with LastFmClientAdapter(
        client_api_key="dummy-api-key",
        client_secret="dummy-client-secret",
        base_url=HttpUrl(base_url) if base_url else None,
    ) as client:
        yield client


# --- Services ---


@pytest.fixture
def track_reconciler() -> TrackReconciler:
    return TrackReconciler()


# --- Wiremock ---


@pytest.fixture
def spotify_wiremock() -> Iterable[WireMockContext]:
    with WireMockContext(base_url=os.getenv("WIREMOCK_SPOTIFY_ADMIN_URL", "")) as wiremock_context:
        yield wiremock_context


@pytest.fixture
def lastfm_wiremock() -> Iterable[WireMockContext]:
    with WireMockContext(base_url=os.getenv("WIREMOCK_LASTFM_ADMIN_URL", "")) as wiremock_context:
        yield wiremock_context


# --- Security impl helper ---


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_access_token_manager() -> AccessTokenManagerPort:
    return JwtAccessTokenManager()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()
