import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.session import async_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.security import Argon2PasswordHasher
from museflow.infrastructure.adapters.security import JwtAccessTokenManager
from museflow.infrastructure.adapters.security import SystemStateTokenGenerator
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.spotify import spotify_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{app_settings.API_V1_PREFIX}/users/login")


def get_password_hasher() -> PasswordHasherPort:
    return Argon2PasswordHasher()


def get_access_token_manager() -> AccessTokenManagerPort:
    return JwtAccessTokenManager()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return SystemStateTokenGenerator()


async def get_db() -> AsyncGenerator[AsyncSession]:  # pragma: no cover
    """Raw session for the health check only: everything else goes through the unit of work."""
    async with async_session_factory() as session:
        yield session


def get_unit_of_work() -> UnitOfWorkPort:
    # FastAPI caches it for the request, whose steps run one after another.
    return SQLUnitOfWork(async_session_factory)


async def get_provider_oauth(provider: MusicProvider) -> AsyncGenerator[ProviderOAuthPort]:
    match provider:
        case MusicProvider.SPOTIFY:
            async with SpotifyOAuthAdapter(
                client_id=spotify_settings.CLIENT_ID,
                client_secret=spotify_settings.CLIENT_SECRET.get_secret_value(),
                redirect_uri=spotify_settings.REDIRECT_URI,
                base_url=spotify_settings.BASE_URL,
                auth_endpoint=spotify_settings.AUTH_ENDPOINT,
                token_endpoint=spotify_settings.TOKEN_ENDPOINT,
                timeout=spotify_settings.HTTP_TIMEOUT,
                token_buffer_seconds=spotify_settings.TOKEN_BUFFER_SECONDS,
                max_retry_wait=spotify_settings.HTTP_MAX_RETRY_WAIT,
            ) as provider_oauth:
                yield provider_oauth
        case _:
            raise ValueError(f"Unknown provider: {provider}")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
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

    async with uow:
        user = await uow.users.get_by_id(uuid.UUID(user_id))
    if user is None:
        logger.debug("No user associated to the token", extra={"user_id": str(user_id)})
        raise credentials_exception

    return user


async def get_user_from_state(
    state: str,
    provider: MusicProvider,
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
) -> User:
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    async with uow:
        auth_state = await uow.auth_states.consume(state=state)
        user = await uow.users.get_by_id(auth_state.user_id) if auth_state else None

    # The route takes its provider from the URL: a state only answers for the provider it was issued for.
    if not auth_state or auth_state.provider != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if not user:
        raise HTTPException(status_code=400, detail="Unable to load user from state")

    return user
