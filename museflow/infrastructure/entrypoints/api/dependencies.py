import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated
from typing import Final

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi.security import OAuth2PasswordBearer

from pydantic import AnyUrl

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import jwt

from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.storage import FileStoragePort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.config.settings.spotify import spotify_settings
from museflow.infrastructure.entrypoints.api.const import API_V1_PREFIX
from museflow.infrastructure.entrypoints.api.const import PAGE_LIMIT_DEFAULT
from museflow.infrastructure.entrypoints.api.const import PAGE_LIMIT_MAX
from museflow.infrastructure.entrypoints.api.schemas import PageParams
from museflow.infrastructure.entrypoints.wiring import Wiring

logger = logging.getLogger(__name__)

oauth2_scheme: Final[OAuth2PasswordBearer] = OAuth2PasswordBearer(tokenUrl=f"{API_V1_PREFIX}/users/login")


def get_wiring(request: Request) -> Wiring:
    # Opened by the lifespan, for the process.
    wiring: Wiring = request.app.state.wiring
    return wiring


def get_session_factory(wiring: Annotated[Wiring, Depends(get_wiring)]) -> async_sessionmaker[AsyncSession]:
    return wiring.session_factory


def get_unit_of_work(wiring: Annotated[Wiring, Depends(get_wiring)]) -> UnitOfWorkPort:
    # FastAPI caches it for the request, whose steps run one after another.
    return wiring.build_unit_of_work()


def get_password_hasher(wiring: Annotated[Wiring, Depends(get_wiring)]) -> PasswordHasherPort:
    return wiring.build_password_hasher()


def get_access_token_manager(wiring: Annotated[Wiring, Depends(get_wiring)]) -> AccessTokenManagerPort:
    return wiring.build_access_token_manager()


def get_state_token_generator(wiring: Annotated[Wiring, Depends(get_wiring)]) -> StateTokenGeneratorPort:
    return wiring.build_state_token_generator()


def get_file_storage(wiring: Annotated[Wiring, Depends(get_wiring)]) -> FileStoragePort:
    return wiring.build_file_storage()


def get_page_params(
    limit: Annotated[
        int, Query(ge=1, le=PAGE_LIMIT_MAX, description="How many items the page holds")
    ] = PAGE_LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0, description="How many items to skip, from the start of the collection")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


def get_redirect_uri(
    provider: MusicProvider,
    redirect_uri: Annotated[
        AnyUrl, Query(description="Where the provider sends the browser back: the client's page or app")
    ],
) -> AnyUrl:
    # Only the clients registered with the provider: any other URI would send the code to someone else.
    match provider:
        case MusicProvider.SPOTIFY:
            allowed_uris = spotify_settings.REDIRECT_URIS
        case _:
            raise ValueError(f"Unknown provider: {provider}")

    if str(redirect_uri) not in {str(uri) for uri in allowed_uris}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Redirect URI not allowed")

    return redirect_uri


async def get_provider_oauth(
    provider: MusicProvider,
    redirect_uri: Annotated[AnyUrl, Depends(get_redirect_uri)],
    wiring: Annotated[Wiring, Depends(get_wiring)],
) -> AsyncGenerator[ProviderOAuthPort]:
    async with wiring.build_provider_oauth(provider, redirect_uri) as provider_oauth:
        yield provider_oauth


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    uow: Annotated[UnitOfWorkPort, Depends(get_unit_of_work)],
    access_token_manager: Annotated[AccessTokenManagerPort, Depends(get_access_token_manager)],
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


# What several routes take: the dependency rides on the type.
UnitOfWorkDep = Annotated[UnitOfWorkPort, Depends(get_unit_of_work)]
PasswordHasherDep = Annotated[PasswordHasherPort, Depends(get_password_hasher)]
AccessTokenManagerDep = Annotated[AccessTokenManagerPort, Depends(get_access_token_manager)]
ProviderOAuthDep = Annotated[ProviderOAuthPort, Depends(get_provider_oauth)]
FileStorageDep = Annotated[FileStoragePort, Depends(get_file_storage)]
PageParamsDep = Annotated[PageParams, Depends(get_page_params)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
