from collections.abc import AsyncGenerator
from unittest import mock

from pydantic import HttpUrl

import pytest

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.ports.repositories.music import ArtistRepository
from museflow.domain.ports.repositories.music import TrackRepository
from museflow.domain.ports.repositories.users import UserRepository
from museflow.domain.ports.security import AccessTokenManagerPort
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.schemas.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.unit.factories.entities.auth import OAuthProviderStateFactory
from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.factories.schemas.auth import OAuthProviderTokenPayloadFactory

# --- Security Mocks ---


@pytest.fixture
def mock_password_hasher() -> mock.Mock:
    return mock.Mock(spec=PasswordHasherPort)


@pytest.fixture
def mock_access_token_manager() -> mock.Mock:
    return mock.Mock(spec=AccessTokenManagerPort)


@pytest.fixture
def mock_state_token_generator() -> mock.Mock:
    return mock.Mock(spec=StateTokenGeneratorPort)


# --- Repository Mocks ---


@pytest.fixture
def mock_user_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=UserRepository)


@pytest.fixture
def mock_auth_state_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=OAuthProviderStateRepository)


@pytest.fixture
def mock_auth_token_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=OAuthProviderTokenRepository)


@pytest.fixture
def mock_artist_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=ArtistRepository)


@pytest.fixture
def mock_track_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=TrackRepository)


# --- Entity Mocks ---


@pytest.fixture
def user(request: pytest.FixtureRequest) -> User:
    return UserFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def token_payload(request: pytest.FixtureRequest) -> OAuthProviderTokenPayload:
    return OAuthProviderTokenPayloadFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def auth_state(request: pytest.FixtureRequest, user: User) -> OAuthProviderState:
    params = getattr(request, "param", {})
    params.setdefault("user_id", user.id)

    return OAuthProviderStateFactory.build(**params)


@pytest.fixture
def auth_token(request: pytest.FixtureRequest, user: User) -> OAuthProviderUserToken:
    params = getattr(request, "param", {})
    params.setdefault("user_id", user.id)

    return OAuthProviderUserTokenFactory.build(**params)


# --- Client Mocks ---


@pytest.fixture
def mock_provider_client(token_payload: OAuthProviderTokenPayload) -> mock.AsyncMock:
    return mock.AsyncMock(
        spec=ProviderOAuthClientPort,
        refresh_access_token=mock.AsyncMock(return_value=token_payload),
    )


# --- Adapters ---


@pytest.fixture
async def spotify_client() -> AsyncGenerator[SpotifyOAuthClientAdapter]:
    async with SpotifyOAuthClientAdapter(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        redirect_uri=HttpUrl("http://127.0.0.1:8000/api/v1/spotify/callback"),
    ) as client:
        yield client


@pytest.fixture
def spotify_session_client(
    user: User,
    auth_token: OAuthProviderUserToken,
    mock_auth_token_repository: mock.AsyncMock,
    spotify_client: SpotifyOAuthClientAdapter,
) -> SpotifyOAuthSessionClient:
    return SpotifyOAuthSessionClient(
        user=user,
        auth_token=auth_token,
        auth_token_repository=mock_auth_token_repository,
        client=spotify_client,
    )


@pytest.fixture
def spotify_library(
    user: User,
    spotify_session_client: SpotifyOAuthSessionClient,
) -> SpotifyLibraryAdapter:
    return SpotifyLibraryAdapter(
        user=user,
        session_client=spotify_session_client,
        max_concurrency=10,
    )
