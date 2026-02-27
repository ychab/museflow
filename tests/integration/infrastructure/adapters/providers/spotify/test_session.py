from datetime import datetime
from datetime import timedelta
from unittest import mock

from httpx import codes

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.schemas.auth import OAuthProviderTokenPayload
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory


class TestSpotifyOAuthSessionClient:
    """
    These integration tests are focus on data persistence and protocol flow (HTTP 401 -> Refresh -> Retry).
    """

    @pytest.fixture
    def auth_token_expired(
        self,
        frozen_time: datetime,
        spotify_session_client: SpotifyOAuthSessionClient,
    ) -> OAuthProviderUserToken:
        return OAuthProviderUserTokenFactory.build(
            token_expires_at=frozen_time - timedelta(seconds=spotify_session_client.token_buffer_seconds + 20),
        )

    async def test__execute__proactive_refresh(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: mock.AsyncMock,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=str(spotify_session_client.client.token_endpoint),
            method="POST",
            json={
                "token_type": token_payload.token_type,
                "access_token": token_payload.access_token,
                "refresh_token": token_payload.refresh_token,
                "expires_in": 3600,
            },
        )
        httpx_mock.add_response(
            url=f"{spotify_session_client.client.base_url}/test",
            method="GET",
            json={},
        )
        spotify_session_client.auth_token = auth_token_expired

        await spotify_session_client.execute("GET", "/test")

        # Check that user token is refresh in memory.
        assert spotify_session_client.auth_token.token_type == token_payload.token_type
        assert spotify_session_client.auth_token.token_access == token_payload.access_token
        assert spotify_session_client.auth_token.token_refresh == token_payload.refresh_token
        assert spotify_session_client.auth_token.token_expires_at == frozen_time + timedelta(seconds=3600)

        # Check that user token is refresh in DB.
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == spotify_session_client.user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result = await async_session_db.execute(stmt)
        auth_token_db = result.scalar_one()

        assert auth_token_db is not None
        assert auth_token_db.token_type == token_payload.token_type
        assert auth_token_db.token_access == token_payload.access_token
        assert auth_token_db.token_refresh == token_payload.refresh_token
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)

    async def test__execute__reactive_refresh_on_401(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: mock.AsyncMock,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
        httpx_mock: HTTPXMock,
    ) -> None:
        # Mock: First call fails (401), second call refresh succeeds, Second call succeeds
        httpx_mock.add_response(
            url=f"{spotify_session_client.client.base_url}/test",
            method="GET",
            status_code=codes.UNAUTHORIZED,
        )
        httpx_mock.add_response(
            url=str(spotify_session_client.client.token_endpoint),
            method="POST",
            json={
                "token_type": token_payload.token_type,
                "access_token": token_payload.access_token,
                "refresh_token": token_payload.refresh_token,
                "expires_in": 3600,
            },
        )
        httpx_mock.add_response(
            url=f"{spotify_session_client.client.base_url}/test",
            method="GET",
            json={},
        )

        await spotify_session_client.execute("GET", "/test")

        # Check that user token is refresh in memory.
        assert spotify_session_client.auth_token.token_type == token_payload.token_type
        assert spotify_session_client.auth_token.token_access == token_payload.access_token
        assert spotify_session_client.auth_token.token_refresh == token_payload.refresh_token
        assert spotify_session_client.auth_token.token_expires_at == frozen_time + timedelta(seconds=3600)

        # Check that user token is refresh in DB.
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == spotify_session_client.user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result = await async_session_db.execute(stmt)
        auth_token_db = result.scalar_one()

        assert auth_token_db is not None
        assert auth_token_db.token_type == token_payload.token_type
        assert auth_token_db.token_access == token_payload.access_token
        assert auth_token_db.token_refresh == token_payload.refresh_token
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)
