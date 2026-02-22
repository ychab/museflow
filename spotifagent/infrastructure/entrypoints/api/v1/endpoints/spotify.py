from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import RedirectResponse

from spotifagent.application.use_cases.oauth_callback import oauth_callback
from spotifagent.application.use_cases.oauth_redirect import oauth_redirect
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import ProviderExchangeCodeError
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort
from spotifagent.infrastructure.entrypoints.api.dependencies import get_auth_state_repository
from spotifagent.infrastructure.entrypoints.api.dependencies import get_current_user
from spotifagent.infrastructure.entrypoints.api.dependencies import get_spotify_account_repository
from spotifagent.infrastructure.entrypoints.api.dependencies import get_spotify_client
from spotifagent.infrastructure.entrypoints.api.dependencies import get_state_token_generator
from spotifagent.infrastructure.entrypoints.api.dependencies import get_user_from_state
from spotifagent.infrastructure.entrypoints.api.schemas import SuccessResponse

router = APIRouter()


@router.get("/connect", name="spotify_connect")
async def connect(
    current_user: User = Depends(get_current_user),
    auth_state_repository: OAuthProviderStateRepositoryPort = Depends(get_auth_state_repository),
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
    spotify_account_repository: SpotifyAccountRepositoryPort = Depends(get_spotify_account_repository),
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
            spotify_account_repository=spotify_account_repository,
            provider_client=spotify_client,
        )
    except ProviderExchangeCodeError as e:
        raise HTTPException(status_code=400, detail="Failed to exchange code") from e

    return SuccessResponse(message="Spotify account linked successfully")
