from pydantic import HttpUrl

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.use_cases.provider_oauth_redirect import oauth_redirect
from museflow.domain.entities.user import User
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter


class TestSpotifyOAuthRedirectUseCase:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        auth_state_repository: OAuthProviderStateRepository,
        spotify_client: SpotifyOAuthClientAdapter,
        state_token_generator: StateTokenGeneratorPort,
    ) -> None:
        authorization_url = await oauth_redirect(
            user=user,
            auth_state_repository=auth_state_repository,
            provider=MusicProvider.SPOTIFY,
            provider_client=spotify_client,
            state_token_generator=state_token_generator,
        )
        assert isinstance(authorization_url, HttpUrl)

        stmt = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result = await async_session_db.execute(stmt)
        auth_state_db = result.scalar_one_or_none()

        assert auth_state_db is not None
        assert auth_state_db.state is not None
