from collections.abc import AsyncGenerator
from unittest import mock

from pydantic import HttpUrl

import pytest

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.ports.repositories.users import UserRepository
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmAdvisorAdapter
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.unit.factories.entities.auth import OAuthProviderStateFactory
from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.factories.value_objects.auth import OAuthProviderTokenPayloadFactory

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


@pytest.fixture
def mock_taste_profile_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=TasteProfileRepository)


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
def mock_provider_oauth(token_payload: OAuthProviderTokenPayload) -> mock.AsyncMock:
    return mock.AsyncMock(
        spec=SpotifyOAuthAdapter,
        refresh_access_token=mock.AsyncMock(return_value=token_payload),
    )


@pytest.fixture
def mock_provider_library() -> mock.AsyncMock:
    return mock.AsyncMock(spec=ProviderLibraryPort)


@pytest.fixture
def mock_advisor_client() -> mock.AsyncMock:
    return mock.AsyncMock(spec=AdvisorClientPort)


# --- Service Mocks ---


@pytest.fixture
def mock_track_reconciler() -> mock.Mock:
    return mock.Mock(spec=TrackReconciler)


# --- Adapters ---


@pytest.fixture
async def spotify_oauth() -> AsyncGenerator[SpotifyOAuthAdapter]:
    async with SpotifyOAuthAdapter(
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
        redirect_uri=HttpUrl("http://127.0.0.1:8000/api/v1/spotify/callback"),
        max_retry_wait=5,
    ) as client:
        yield client


@pytest.fixture
def spotify_session_client(
    user: User,
    auth_token: OAuthProviderUserToken,
    mock_auth_token_repository: mock.AsyncMock,
    spotify_oauth: SpotifyOAuthAdapter,
) -> SpotifyOAuthSessionClient:
    return SpotifyOAuthSessionClient(
        user=user,
        auth_token=auth_token,
        auth_token_repository=mock_auth_token_repository,
        oauth_client=spotify_oauth,
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


@pytest.fixture
async def lastfm_advisor() -> AsyncGenerator[LastFmAdvisorAdapter]:
    async with LastFmAdvisorAdapter(
        client_api_key="dummy-api-key",
        client_secret="dummy-client-secret",
    ) as client:
        yield client


@pytest.fixture
async def gemini_advisor() -> AsyncGenerator[GeminiAdvisorAdapter]:
    async with GeminiAdvisorAdapter(
        api_key="dummy-api-key",
        model=GeminiModel.FLASH_2_5,
        max_retry_wait=5,
    ) as client:
        yield client


@pytest.fixture
async def gemini_profiler() -> AsyncGenerator[GeminiTasteProfileAdapter]:
    async with GeminiTasteProfileAdapter(
        api_key="dummy-api-key",
        model=GeminiModel.FLASH_2_5,
        max_retry_wait=5,
    ) as client:
        yield client


# --- Services ---


@pytest.fixture
def track_reconciler(request: pytest.FixtureRequest) -> TrackReconciler:
    params = getattr(request, "param", {})
    match_threshold = params.get("match_threshold", 80.0)
    score_minimum = params.get("score_minimum", 60.0)

    return TrackReconciler(match_threshold=match_threshold, score_minimum=score_minimum)
