from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.use_cases.provider_oauth_code_exchange import exchange_oauth_code
from museflow.application.use_cases.provider_oauth_redirect_url_build import build_oauth_redirect_url
from museflow.application.use_cases.provider_oauth_state_consume import consume_oauth_state
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import ProviderOAuthDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.dependencies import get_state_token_generator
from museflow.infrastructure.entrypoints.api.v1.schemas.common import SuccessResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.provider import ProviderConnectCompleteRequest
from museflow.infrastructure.entrypoints.api.v1.schemas.provider import ProviderConnectResponse

router = APIRouter()


@router.post("/connect", name="provider_connect")
async def connect(
    provider: MusicProvider,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
    provider_oauth: ProviderOAuthDep,
    state_token_generator: Annotated[StateTokenGeneratorPort, Depends(get_state_token_generator)],
) -> ProviderConnectResponse:
    """Starts the OAuth flow: the client opens the URL, and the provider sends the browser back to `redirect_uri`.

    The provider never calls the API: the client reads the code and the state back from its redirect URI, then hands
    them to `connect/complete` with its own Bearer token.
    """
    authorization_url = await build_oauth_redirect_url(
        user=current_user,
        uow=uow,
        provider=provider,
        provider_oauth=provider_oauth,
        state_token_generator=state_token_generator,
    )
    return ProviderConnectResponse(authorization_url=authorization_url)


@router.post("/connect/complete", name="provider_connect_complete")
async def connect_complete(
    provider: MusicProvider,
    payload: ProviderConnectCompleteRequest,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
    provider_oauth: ProviderOAuthDep,
) -> SuccessResponse:
    """Ends the OAuth flow: stores the provider tokens of the user who started it, and of no one else.

    The state must have been issued to the user of the Bearer token: a code obtained by someone else, sent to this
    user, can't link that person's provider account to the wrong user (#101). `redirect_uri` is the one of `connect`:
    the provider refuses the exchange otherwise.
    """
    await consume_oauth_state(state=payload.state, user=current_user, provider=provider, uow=uow)

    await exchange_oauth_code(
        code=payload.code,
        user=current_user,
        provider=provider,
        uow=uow,
        provider_oauth=provider_oauth,
    )

    return SuccessResponse(message=f"{provider.title()} account linked successfully")
