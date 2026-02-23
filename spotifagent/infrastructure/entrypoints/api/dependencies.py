import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import AccessTokenManagerPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort
from spotifagent.infrastructure.adapters.database.repositories.auth import OAuthProviderStateRepository
from spotifagent.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenRepository
from spotifagent.infrastructure.adapters.database.repositories.users import UserRepository
from spotifagent.infrastructure.adapters.database.session import session_scope
from spotifagent.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from spotifagent.infrastructure.adapters.security import Argon2PasswordHasher
from spotifagent.infrastructure.adapters.security import JwtAccessTokenManager
from spotifagent.infrastructure.adapters.security import SystemStateTokenGenerator
from spotifagent.infrastructure.config.settings.app import app_settings
from spotifagent.infrastructure.config.settings.spotify import spotify_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{app_settings.API_V1_PREFIX}/users/login")


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_access_token_manager() -> AccessTokenManagerPort:
    return JwtAccessTokenManager()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


async def get_db() -> AsyncGenerator[AsyncSession]:  # pragma: no cover
    async with session_scope() as session:
        yield session


def get_auth_state_repository(session: AsyncSession = Depends(get_db)) -> OAuthProviderStateRepositoryPort:
    return OAuthProviderStateRepository(session)


def get_auth_token_repository(session: AsyncSession = Depends(get_db)) -> OAuthProviderTokenRepositoryPort:
    return OAuthProviderTokenRepository(session)


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepositoryPort:
    return UserRepository(session)


async def get_spotify_client() -> AsyncGenerator[ProviderOAuthClientPort]:
    async with SpotifyOAuthClientAdapter(
        client_id=spotify_settings.CLIENT_ID,
        client_secret=spotify_settings.CLIENT_SECRET,
        redirect_uri=spotify_settings.REDIRECT_URI,
        timeout=spotify_settings.HTTP_TIMEOUT,
        token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
    ) as spotify_client:
        yield spotify_client


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> User:
    logger = logging.getLogger(f"{__name__}.get_current_user")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = access_token_manager.decode(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid token")
        raise credentials_exception from exc

    user_id: str = payload.get("sub", "")
    if not user_id:
        logger.debug("No user ID found in token")
        raise credentials_exception

    user = await user_repository.get_by_id(uuid.UUID(user_id))
    if user is None:
        logger.debug("No user associated to the token")
        raise credentials_exception

    return user


async def get_user_from_state(
    state: str,
    auth_state_repository: OAuthProviderStateRepositoryPort = Depends(get_auth_state_repository),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
) -> User:
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    auth_state = await auth_state_repository.consume(state=state)
    if not auth_state:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    user = await user_repository.get_by_id(auth_state.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Unable to load user from state")

    return user
