from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_oauth_code_exchange import exchange_oauth_code
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.database.models import AuthProviderStateModel
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter

from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("spotify")
class TestExchangeOAuthCodeUseCase:
    async def test__token_payload__create(
        self,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
        auth_token_repository: OAuthProviderTokenRepository,
        frozen_time: datetime,
        user: User,
        token_payload: OAuthProviderTokenPayload,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=200,
            json_body={
                "token_type": token_payload.token_type,
                "access_token": token_payload.access_token,
                "refresh_token": token_payload.refresh_token,
                "expires_in": 3600,
            },
        )

        await exchange_oauth_code(
            code="test",
            user=user,
            provider=MusicProvider.SPOTIFY,
            uow=uow,
            provider_oauth=spotify_oauth,
        )

        stmt_state = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_state = await async_session_db.execute(stmt_state)
        auth_state_db = result_state.scalar_one_or_none()
        assert auth_state_db is None

        saved_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)

        assert saved_token is not None
        assert saved_token.token_type == token_payload.token_type
        assert saved_token.token_access == token_payload.access_token
        assert saved_token.token_refresh == token_payload.refresh_token
        assert saved_token.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.parametrize("auth_token", [{"provider": MusicProvider.SPOTIFY}], indirect=["auth_token"])
    async def test__token_payload__update(
        self,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
        auth_token_repository: OAuthProviderTokenRepository,
        frozen_time: datetime,
        user: User,
        token_payload: OAuthProviderTokenPayload,
        auth_token: OAuthProviderUserToken,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=200,
            json_body={
                "token_type": token_payload.token_type,
                "access_token": token_payload.access_token,
                "refresh_token": token_payload.refresh_token,
                "expires_in": 3600,
            },
        )

        await exchange_oauth_code(
            code="test",
            user=user,
            provider=MusicProvider.SPOTIFY,
            uow=uow,
            provider_oauth=spotify_oauth,
        )

        stmt_state = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_state = await async_session_db.execute(stmt_state)
        auth_state_db = result_state.scalar_one_or_none()
        assert auth_state_db is None

        saved_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)

        assert saved_token is not None
        assert saved_token.token_type == token_payload.token_type
        assert saved_token.token_access == token_payload.access_token
        assert saved_token.token_refresh == token_payload.refresh_token
        assert saved_token.token_expires_at == frozen_time + timedelta(seconds=3600)
