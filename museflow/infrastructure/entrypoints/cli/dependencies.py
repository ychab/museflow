from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.users import UserRepository
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import MusicAdvisor
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiClientAdapter
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmClientAdapter
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderStateSQLRepository
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import ArtistSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import TrackSQLRepository
from museflow.infrastructure.adapters.database.repositories.users import UserSQLRepository
from museflow.infrastructure.adapters.database.session import session_scope
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.gemini import gemini_settings
from museflow.infrastructure.config.settings.lastfm import lastfm_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings

# --- Security ---


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


# --- Context manager ---


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession]:
    async with session_scope() as session:
        yield session


@asynccontextmanager
async def get_spotify_oauth() -> AsyncGenerator[SpotifyOAuthAdapter]:
    async with SpotifyOAuthAdapter(
        client_id=spotify_settings.CLIENT_ID,
        client_secret=spotify_settings.CLIENT_SECRET,
        redirect_uri=spotify_settings.REDIRECT_URI,
        base_url=spotify_settings.BASE_URL,
        auth_endpoint=spotify_settings.AUTH_ENDPOINT,
        token_endpoint=spotify_settings.TOKEN_ENDPOINT,
        timeout=spotify_settings.HTTP_TIMEOUT,
        token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
        max_retry_wait=spotify_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


@asynccontextmanager
async def get_lastfm_client() -> AsyncGenerator[AdvisorClientPort]:
    async with LastFmClientAdapter(
        client_api_key=lastfm_settings.CLIENT_API_KEY,
        client_secret=lastfm_settings.CLIENT_SECRET,
        base_url=lastfm_settings.BASE_URL,
        timeout=lastfm_settings.HTTP_TIMEOUT,
    ) as client:
        yield client


@asynccontextmanager
async def get_gemini_client() -> AsyncGenerator[AdvisorClientPort]:
    async with GeminiClientAdapter(
        api_key=gemini_settings.API_KEY,
        model=gemini_settings.MODEL,
        base_url=gemini_settings.BASE_URL,
        timeout=gemini_settings.HTTP_TIMEOUT,
        max_retry_wait=gemini_settings.HTTP_MAX_RETRY_WAIT,
    ) as client:
        yield client


@asynccontextmanager
async def get_advisor_client(advisor: MusicAdvisor) -> AsyncGenerator[AdvisorClientPort]:
    match advisor:
        case MusicAdvisor.LASTFM:
            async with get_lastfm_client() as client:
                yield client
        case MusicAdvisor.GEMINI:
            async with get_gemini_client() as client:
                yield client
        case _:
            raise ValueError(f"Unknown advisor: {advisor}")


# --- Session manager ---


def get_spotify_library_factory(
    session: AsyncSession,
    spotify_client: SpotifyOAuthAdapter,
) -> SpotifyLibraryFactory:
    return SpotifyLibraryFactory(
        auth_token_repository=get_auth_token_repository(session),
        oauth_client=spotify_client,
    )


# --- Repositories ---


def get_user_repository(session: AsyncSession) -> UserRepository:
    return UserSQLRepository(session)


def get_auth_state_repository(session: AsyncSession) -> OAuthProviderStateRepository:
    return OAuthProviderStateSQLRepository(session)


def get_auth_token_repository(session: AsyncSession) -> OAuthProviderTokenRepository:
    return OAuthProviderTokenSQLRepository(session)


def get_artist_repository(session: AsyncSession) -> ArtistRepository:
    return ArtistSQLRepository(session)


def get_track_repository(session: AsyncSession) -> TrackRepository:
    return TrackSQLRepository(session)


# --- Services ---


def get_track_reconciler() -> TrackReconciler:
    return TrackReconciler(
        match_threshold=app_settings.RECONCILER_TRACK_MATCH_THRESHOLD,
        score_minimum=app_settings.RECONCILER_TRACK_SCORE_MINIMUM,
    )
