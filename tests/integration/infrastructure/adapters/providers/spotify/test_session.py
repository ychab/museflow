import logging
from dataclasses import replace
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.database.models import AuthProviderTokenModel
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("spotify")
class TestSpotifyOAuthSessionClient:
    """
    These integration tests are focus on data persistence and protocol flow (HTTP 401 -> Refresh -> Retry).
    """

    @pytest.fixture
    def auth_token_expired(
        self,
        frozen_time: datetime,
        auth_token: OAuthProviderUserToken,
        spotify_session_client: SpotifyOAuthSessionClient,
    ) -> OAuthProviderUserToken:
        """The stored token as the session holds it, past its expiry."""
        return replace(
            auth_token,
            token_expires_at=frozen_time - timedelta(seconds=spotify_session_client.token_buffer_seconds + 20),
        )

    async def test__execute__proactive_refresh(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
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
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/test",
            status=200,
            json_body={},
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
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
        spotify_wiremock: WireMockContext,
    ) -> None:
        # Mock: First call fails (401), second call refresh succeeds, Second call succeeds
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/test",
            status=401,
            scenario_name="reactive_refresh",
            required_state="Started",
            new_state="Authorized",
        )
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
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/test",
            status=200,
            scenario_name="reactive_refresh",
            required_state="Authorized",
            json_body={},
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

    async def test__execute__refresh__token_replaced_meanwhile(
        self,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
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
        spotify_wiremock.create_mapping(method="GET", url_path="/test", status=200, json_body={})
        spotify_session_client.auth_token = auth_token_expired
        # Another session reconnects the user while this one holds the expired token.
        auth_token_reconnected = await auth_token_repository.upsert(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        await spotify_session_client.execute("GET", "/test")

        # The newer token wins over this session's refresh, in the database and in memory.
        auth_token_stored = await auth_token_repository.get(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
        )
        assert auth_token_stored == auth_token_reconnected
        assert spotify_session_client.auth_token == auth_token_reconnected

    async def test__execute__refresh__token_deleted_meanwhile(
        self,
        frozen_time: datetime,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        token_payload: OAuthProviderTokenPayload,
        auth_token_expired: OAuthProviderUserToken,
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
        spotify_wiremock.create_mapping(method="GET", url_path="/test", status=200, json_body={})
        spotify_session_client.auth_token = auth_token_expired
        # Another session got `invalid_grant` for the refresh token this refresh rotates, and deleted the stored token
        # before this one was saved.
        await auth_token_repository.delete(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
            expected_token_refresh=auth_token_expired.token_refresh,
        )

        await spotify_session_client.execute("GET", "/test")

        # The token Spotify just issued is saved again, not lost.
        auth_token_stored = await auth_token_repository.get(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
        )
        assert auth_token_stored is not None
        assert auth_token_stored.token_access == token_payload.access_token
        assert auth_token_stored.token_refresh == token_payload.refresh_token
        assert auth_token_stored.token_expires_at == frozen_time + timedelta(seconds=3600)
        assert spotify_session_client.auth_token == auth_token_stored

    async def test__execute__refresh__invalid_grant__token_replaced_meanwhile(
        self,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_expired: OAuthProviderUserToken,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=400,
            json_body={"error": "invalid_grant"},
        )
        spotify_wiremock.create_mapping(method="GET", url_path="/test", status=200, json_body={})
        spotify_session_client.auth_token = auth_token_expired
        # Another session rotated the refresh token: Spotify now rejects the one this session holds.
        auth_token_rotated = await auth_token_repository.upsert(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        await spotify_session_client.execute("GET", "/test")

        # The rotated token is kept, not discarded with the rejected one.
        auth_token_stored = await auth_token_repository.get(
            user_id=auth_token_expired.user_id,
            provider=MusicProvider.SPOTIFY,
        )
        assert auth_token_stored == auth_token_rotated
        assert spotify_session_client.auth_token == auth_token_rotated

    async def test__execute__refresh__invalid_grant(
        self,
        user: User,
        spotify_oauth: SpotifyOAuthAdapter,
        spotify_session_client: SpotifyOAuthSessionClient,
        auth_token_repository: OAuthProviderTokenRepository,
        auth_token_expired: OAuthProviderUserToken,
        spotify_wiremock: WireMockContext,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=400,
            json_body={"error": "invalid_grant"},
        )
        spotify_session_client.auth_token = auth_token_expired

        with caplog.at_level(logging.WARNING), pytest.raises(ProviderAuthTokenNotFoundError):
            await spotify_session_client.execute("GET", "/test")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].__dict__["user_id"] == str(user.id)
        assert caplog.records[0].__dict__["provider"] == MusicProvider.SPOTIFY

        assert (
            await auth_token_repository.get(user_id=auth_token_expired.user_id, provider=MusicProvider.SPOTIFY) is None
        )
