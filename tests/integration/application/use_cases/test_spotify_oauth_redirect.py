from pydantic import HttpUrl

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.application.use_cases.spotify_oauth_redirect import spotify_oauth_redirect
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort
from spotifagent.infrastructure.adapters.clients.spotify import SpotifyClientAdapter
from spotifagent.infrastructure.adapters.database.models import User as UserModel


class TestSpotifyOAuthRedirectUseCase:
    @pytest.mark.parametrize("user", [{"spotify_state": None}], indirect=["user"])
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        user_repository: UserRepositoryPort,
        spotify_client: SpotifyClientAdapter,
        state_token_generator: StateTokenGeneratorPort,
    ) -> None:
        assert user.spotify_state is None

        authorization_url = await spotify_oauth_redirect(
            user=user,
            user_repository=user_repository,
            spotify_client=spotify_client,
            state_token_generator=state_token_generator,
        )
        assert isinstance(authorization_url, HttpUrl)

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one_or_none()

        assert user_db is not None
        assert user_db.spotify_state is not None
