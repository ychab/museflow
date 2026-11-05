import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import RedirectResponse

from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_oauth_callback import oauth_callback
from museflow.application.use_cases.provider_oauth_redirect import oauth_redirect
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.api.dependencies import get_state_token_generator
from museflow.infrastructure.entrypoints.api.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.api.dependencies import get_user_from_state
from museflow.infrastructure.entrypoints.api.schemas import SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/connect", name="provider_connect")
async def connect(
    provider: MusicProvider,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    provider_oauth: ProviderOAuthPort = Depends(get_provider_oauth),
    state_token_generator: StateTokenGeneratorPort = Depends(get_state_token_generator),
) -> RedirectResponse:
    authorization_url = await oauth_redirect(
        user=current_user,
        uow=uow,
        provider=provider,
        provider_oauth=provider_oauth,
        state_token_generator=state_token_generator,
    )
    return RedirectResponse(str(authorization_url))


@router.get("/callback", name="provider_callback", status_code=status.HTTP_200_OK)
async def callback(
    provider: MusicProvider,
    code: str | None = None,
    error: str | None = None,
    current_user: User = Depends(get_user_from_state),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    provider_oauth: ProviderOAuthPort = Depends(get_provider_oauth),
) -> SuccessResponse:
    if error:
        logger.warning(
            "OAuth callback error received",
            extra={"user_id": str(current_user.id), "provider": provider, "error": error},
        )
        raise HTTPException(status_code=400, detail="OAuth authorisation failed")
    if not code:
        logger.warning(
            "OAuth callback received without code",
            extra={"user_id": str(current_user.id), "provider": provider},
        )
        raise HTTPException(status_code=400, detail="No authorization code received")

    try:
        await oauth_callback(
            code=code,
            user=current_user,
            provider=provider,
            uow=uow,
            provider_oauth=provider_oauth,
        )
    except ProviderExchangeCodeError as e:
        logger.exception(
            "Failed to exchange OAuth code", extra={"user_id": str(current_user.id), "provider": provider}
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code") from e

    return SuccessResponse(message=f"{provider.title()} account linked successfully")
