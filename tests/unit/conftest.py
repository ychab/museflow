from unittest import mock

import pytest

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderTokenState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.users import User
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from museflow.domain.ports.repositories.music import ArtistRepositoryPort
from museflow.domain.ports.repositories.music import TrackRepositoryPort
from museflow.domain.ports.repositories.users import UserRepositoryPort
from museflow.domain.ports.security import AccessTokenManagerPort
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.ports.security import StateTokenGeneratorPort

from tests.unit.factories.auth import OAuthProviderStateFactory
from tests.unit.factories.auth import OAuthProviderTokenStateFactory
from tests.unit.factories.auth import OAuthProviderUserTokenFactory
from tests.unit.factories.users import UserFactory

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
    return mock.AsyncMock(spec=UserRepositoryPort)


@pytest.fixture
def mock_auth_state_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=OAuthProviderStateRepositoryPort)


@pytest.fixture
def mock_auth_token_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=OAuthProviderTokenRepositoryPort)


@pytest.fixture
def mock_artist_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=ArtistRepositoryPort)


@pytest.fixture
def mock_track_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=TrackRepositoryPort)


# --- Entity Mocks ---


@pytest.fixture
def user(request: pytest.FixtureRequest) -> User:
    return UserFactory.build(**getattr(request, "param", {}))


@pytest.fixture
def token_state(request: pytest.FixtureRequest) -> OAuthProviderTokenState:
    return OAuthProviderTokenStateFactory.build(**getattr(request, "param", {}))


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
def mock_provider_client(token_state: OAuthProviderTokenState) -> mock.AsyncMock:
    return mock.AsyncMock(
        spec=ProviderOAuthClientPort,
        refresh_access_token=mock.AsyncMock(return_value=token_state),
    )
