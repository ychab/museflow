import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Final

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import jwt

from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_oauth_state_consume import consume_oauth_state
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserInactiveError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.wiring import build_access_token_manager
from museflow.infrastructure.entrypoints.wiring import build_password_hasher
from museflow.infrastructure.entrypoints.wiring import build_provider_oauth
from museflow.infrastructure.entrypoints.wiring import build_state_token_generator

logger = logging.getLogger(__name__)

oauth2_scheme: Final[OAuth2PasswordBearer] = OAuth2PasswordBearer(tokenUrl=f"{app_settings.API_V1_PREFIX}/users/login")


def get_password_hasher() -> PasswordHasherPort:
    return build_password_hasher()


def get_access_token_manager() -> AccessTokenManagerPort:
    return build_access_token_manager()


def get_state_token_generator() -> StateTokenGeneratorPort:
    return build_state_token_generator()


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    # Built by the lifespan, which owns the engine.
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return session_factory


def get_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> UnitOfWorkPort:
    # FastAPI caches it for the request, whose steps run one after another.
    return SQLUnitOfWork(session_factory)


async def get_provider_oauth(provider: MusicProvider) -> AsyncGenerator[ProviderOAuthPort]:
    async with build_provider_oauth(provider) as provider_oauth:
        yield provider_oauth


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> User:
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
    if not user.is_active:
        logger.debug("Inactive user", extra={"user_id": str(user_id)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    return user


async def get_user_from_state(
    state: str,
    provider: MusicProvider,
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
) -> User:
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    try:
        return await consume_oauth_state(state=state, provider=provider, uow=uow)
    except ProviderOAuthStateInvalidError as e:
        raise HTTPException(status_code=400, detail="Invalid or expired state") from e
    except UserNotFoundError as e:
        raise HTTPException(status_code=400, detail="Unable to load user from state") from e
    except UserInactiveError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive") from e
