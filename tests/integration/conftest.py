from collections.abc import AsyncGenerator

from pydantic import HttpUrl

from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

import pytest

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.auth import OAuthProviderUserTokenCreate
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.domain.ports.repositories.music import ArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TrackRepositoryPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import AccessTokenManagerPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort
from spotifagent.infrastructure.adapters.database.models import Base
from spotifagent.infrastructure.adapters.database.repositories.auth import OAuthProviderStateRepository
from spotifagent.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenRepository
from spotifagent.infrastructure.adapters.database.repositories.music import ArtistRepository
from spotifagent.infrastructure.adapters.database.repositories.music import TrackRepository
from spotifagent.infrastructure.adapters.database.repositories.users import UserRepository
from spotifagent.infrastructure.adapters.database.session import async_session_factory
from spotifagent.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from spotifagent.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from spotifagent.infrastructure.adapters.security import Argon2PasswordHasher
from spotifagent.infrastructure.adapters.security import JwtAccessTokenManager
from spotifagent.infrastructure.adapters.security import SystemStateTokenGenerator
from spotifagent.infrastructure.config.settings.database import database_settings

from tests.integration.factories.auth import AuthProviderStateModelFactory
from tests.integration.factories.auth import AuthProviderTokenFactory
from tests.integration.factories.base import BaseModelFactory
from tests.integration.factories.users import UserModelFactory
from tests.unit.factories.auth import OAuthProviderTokenStateFactory
from tests.unit.factories.auth import OAuthProviderUserTokenCreateFactory
from tests.unit.factories.users import UserCreateFactory
from tests.unit.factories.users import UserUpdateFactory


@pytest.fixture(scope="session")
def test_db_name() -> str:
    if database_settings.URI is None or not database_settings.URI.path:
        pytest.exit("Missing DATABASE_URI env var (or composites)", 1)
    return f"test_{database_settings.URI.path[1:]}"


@pytest.fixture(scope="session")
async def create_test_database(anyio_backend: str, test_db_name: str) -> AsyncGenerator[None]:
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
    async with async_engine_admin.begin() as async_conn:
        await async_conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    await async_engine_admin.dispose()


@pytest.fixture(scope="session")
async def async_engine(create_test_database, test_db_name: str) -> AsyncGenerator[AsyncEngine]:
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
    Provides an async session that commits data and cleans up via TRUNCATE.

    Use this fixture when you need to test actual database commits or when the
    application code manages its own transactions/connections extensively.

    Pros: Tests 'real' commit behavior.
    Cons: Slower than transaction rollback because of the TRUNCATE operations.
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
    Provides an async session wrapped in a transaction that rolls back after the test.

    This is the default fixture (autouse=True). It is faster than truncation because
    data is never permanently written to disk.
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
def user_repository(async_session_db: AsyncSession) -> UserRepositoryPort:
    return UserRepository(async_session_db)


@pytest.fixture
def auth_state_repository(async_session_db: AsyncSession) -> OAuthProviderStateRepositoryPort:
    return OAuthProviderStateRepository(async_session_db)


@pytest.fixture
def auth_token_repository(async_session_db: AsyncSession) -> OAuthProviderTokenRepositoryPort:
    return OAuthProviderTokenRepository(async_session_db)


@pytest.fixture
def artist_repository(async_session_db: AsyncSession) -> ArtistRepositoryPort:
    return ArtistRepository(async_session_db)


@pytest.fixture
def track_repository(async_session_db: AsyncSession) -> TrackRepositoryPort:
    return TrackRepository(async_session_db)


# --- Entity factories ---


@pytest.fixture
def user_create(request: pytest.FixtureRequest) -> UserCreate:
    return UserCreateFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def user_update(request: pytest.FixtureRequest) -> UserUpdate:
    return UserUpdateFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def token_state(request: pytest.FixtureRequest) -> OAuthProviderTokenState:
    return OAuthProviderTokenStateFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def auth_token_create() -> OAuthProviderUserTokenCreate:
    return OAuthProviderUserTokenCreateFactory.build()


@pytest.fixture
def auth_token_update() -> OAuthProviderUserTokenCreate:
    return OAuthProviderUserTokenCreateFactory.build()


# --- Models DB factories ---


@pytest.fixture
async def user(request: pytest.FixtureRequest) -> User:
    user_db = await UserModelFactory.create_async(**getattr(request, "param", {}))
    return User.model_validate(user_db)


@pytest.fixture
async def auth_state(request: pytest.FixtureRequest, user: User) -> OAuthProviderState:
    params = getattr(request, "param", {})
    params.setdefault("user_id", user.id)

    auth_state_db = await AuthProviderStateModelFactory.create_async(**params)
    return OAuthProviderState.model_validate(auth_state_db)


@pytest.fixture
async def auth_token(request: pytest.FixtureRequest, user: User) -> OAuthProviderUserToken:
    params = getattr(request, "param", {})
    user_id = params.pop("user_id", user.id)
    provider = params.pop("provider", MusicProvider.SPOTIFY)

    auth_token_db = await AuthProviderTokenFactory.create_async(user_id=user_id, provider=provider, **params)
    return OAuthProviderUserToken.model_validate(auth_token_db)


# --- Clients impl ---


@pytest.fixture
async def spotify_client() -> AsyncGenerator[SpotifyOAuthClientAdapter]:
    async with SpotifyOAuthClientAdapter(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        redirect_uri=HttpUrl("http://127.0.0.1:8000/api/v1/spotify/callback"),
    ) as client:
        yield client


# --- Service impl ---


@pytest.fixture
def spotify_library(
    request: pytest.FixtureRequest,
    user: User,
    auth_token: OAuthProviderUserToken,
    auth_token_repository: OAuthProviderTokenRepositoryPort,
    spotify_client: SpotifyOAuthClientAdapter,
) -> SpotifyLibraryAdapter:
    params = getattr(request, "param", {})
    max_concurrency = params.get("max_concurrency", 20)

    return SpotifyLibraryAdapter(
        user=user,
        auth_token=auth_token,
        auth_token_repository=auth_token_repository,
        client=spotify_client,
        max_concurrency=max_concurrency,
    )


# --- Security impl helper ---


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_access_token_manager() -> AccessTokenManagerPort:
    return JwtAccessTokenManager()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()
