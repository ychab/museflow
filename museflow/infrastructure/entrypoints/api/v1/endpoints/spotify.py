from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import RedirectResponse

from museflow.application.use_cases.provider_oauth_callback import oauth_callback
from museflow.application.use_cases.provider_oauth_redirect import oauth_redirect
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.api.dependencies import get_auth_state_repository
from museflow.infrastructure.entrypoints.api.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.api.dependencies import get_state_token_generator
from museflow.infrastructure.entrypoints.api.dependencies import get_user_from_state
from museflow.infrastructure.entrypoints.api.schemas import SuccessResponse

router = APIRouter()


@router.get("/connect", name="spotify_connect")
async def connect(
    current_user: User = Depends(get_current_user),
    auth_state_repository: OAuthProviderStateRepository = Depends(get_auth_state_repository),
    provider_client: ProviderOAuthClientPort = Depends(get_spotify_client),
    state_token_generator: StateTokenGeneratorPort = Depends(get_state_token_generator),
) -> RedirectResponse:
    authorization_url = await oauth_redirect(
        user=current_user,
        auth_state_repository=auth_state_repository,
        provider=MusicProvider.SPOTIFY,
        provider_client=provider_client,
        state_token_generator=state_token_generator,
    )
    return RedirectResponse(str(authorization_url))


@router.get("/callback", name="spotify_callback", status_code=status.HTTP_200_OK)
async def spotify_callback(
    code: str | None = None,
    error: str | None = None,
    current_user: User = Depends(get_user_from_state),
    auth_token_repository: OAuthProviderTokenRepository = Depends(get_auth_token_repository),
    spotify_client: ProviderOAuthClientPort = Depends(get_spotify_client),
) -> SuccessResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    try:
        await oauth_callback(
            code=code,
            user=current_user,
            provider=MusicProvider.SPOTIFY,
            auth_token_repository=auth_token_repository,
            provider_client=spotify_client,
        )
    except ProviderExchangeCodeError as e:
        raise HTTPException(status_code=400, detail="Failed to exchange code") from e

    return SuccessResponse(message="Spotify account linked successfully")
