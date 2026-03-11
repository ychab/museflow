from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.ports.advisors.client import AdvisorClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.ports.repositories.music import ArtistRepository
from museflow.domain.ports.repositories.music import TrackRepository
from museflow.domain.ports.repositories.users import UserRepository
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.types import MusicAdvisor
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmClientAdapter
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderStateSQLRepository
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import ArtistSQLRepository
from museflow.infrastructure.adapters.database.repositories.music import TrackSQLRepository
from museflow.infrastructure.adapters.database.repositories.users import UserSQLRepository
from museflow.infrastructure.adapters.database.session import session_scope
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.lastfm import lastfm_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession]:
    async with session_scope() as session:
        yield session


@asynccontextmanager
async def get_spotify_client() -> AsyncGenerator[SpotifyOAuthClientAdapter]:
    async with SpotifyOAuthClientAdapter(
        client_id=spotify_settings.CLIENT_ID,
        client_secret=spotify_settings.CLIENT_SECRET,
        redirect_uri=spotify_settings.REDIRECT_URI,
        timeout=spotify_settings.HTTP_TIMEOUT,
        token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
    ) as client:
        yield client


@asynccontextmanager
async def get_lastfm_client() -> AsyncGenerator[AdvisorClientPort]:
    async with LastFmClientAdapter(
        client_api_key=lastfm_settings.CLIENT_API_KEY,
        client_secret=lastfm_settings.CLIENT_SECRET,
        timeout=lastfm_settings.HTTP_TIMEOUT,
    ) as client:
        yield client


@asynccontextmanager
async def get_advisor_client(advisor: MusicAdvisor) -> AsyncGenerator[AdvisorClientPort]:
    match advisor:
        case MusicAdvisor.LASTFM:
            async with get_lastfm_client() as client:
                yield client
        case _:
            raise ValueError(f"Unknown advisor: {advisor}")


def get_spotify_library_factory(
    session: AsyncSession,
    spotify_client: SpotifyOAuthClientAdapter,
) -> SpotifyLibraryFactory:
    return SpotifyLibraryFactory(
        auth_token_repository=get_auth_token_repository(session),
        client=spotify_client,
    )


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
