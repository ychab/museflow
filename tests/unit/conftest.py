from collections.abc import AsyncGenerator
from unittest import mock

from pydantic import HttpUrl

import pytest

from museflow.application.inputs.history import StreamingHistoryFileStats
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.ports.repositories.users import UserRepository
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import Reconciler
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.unit.factories.entities.auth import OAuthProviderStateFactory
from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.factories.value_objects.auth import OAuthProviderTokenPayloadFactory
from tests.unit.factories.value_objects.discovery import DiscoveryTasteStrategyFactory

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
def mock_track_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=TrackRepository)


@pytest.fixture
def mock_taste_profile_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=TasteProfileRepository)


@pytest.fixture
def mock_blacklist_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=BlacklistRepository)


@pytest.fixture
def mock_playlist_repository() -> mock.AsyncMock:
    return mock.AsyncMock(spec=PlaylistRepository)


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


@pytest.fixture
def taste_profile(request: pytest.FixtureRequest, user: User) -> TasteProfile:
    params = getattr(request, "param", {})
    params.setdefault("user_id", user.id)

    return TasteProfileFactory.build(**params)


# --- Value objects ---


@pytest.fixture
def discovery_taste_strategy(request: pytest.FixtureRequest) -> DiscoveryTasteStrategy:
    return DiscoveryTasteStrategyFactory.build(**getattr(request, "param", {}))


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
def mock_streaming_history() -> mock.AsyncMock:
    port = mock.AsyncMock(spec=StreamingHistoryPort)
    port.parse_file.return_value = ([], StreamingHistoryFileStats())
    return port


@pytest.fixture
def mock_advisor() -> mock.AsyncMock:
    return mock.AsyncMock(spec=AdvisorPort)


# --- Service Mocks ---


@pytest.fixture
def mock_reconciler() -> mock.Mock:
    return mock.Mock(spec=Reconciler)


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
    )


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
        segment_model=GeminiModel.FLASH_2_5,
        merge_model=GeminiModel.FLASH_2_5,
        reflect_model=GeminiModel.FLASH_2_5,
        max_retry_wait=5,
    ) as client:
        yield client


# --- Services ---


@pytest.fixture
def reconciler(request: pytest.FixtureRequest) -> Reconciler:
    params = getattr(request, "param", {})
    match_threshold = params.get("match_threshold", 80.0)
    score_minimum = params.get("score_minimum", 60.0)

    return Reconciler(match_threshold=match_threshold, score_minimum=score_minimum)
