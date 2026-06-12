from unittest import mock

import httpx
from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter


class TestSpotifyLibraryFactory:
    @pytest.fixture
    def spotify_library_factory(
        self,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_oauth: mock.AsyncMock,
    ) -> SpotifyLibraryFactory:
        return SpotifyLibraryFactory(
            auth_token_repository=mock_auth_token_repository,
            oauth_client=mock_provider_oauth,
        )

    def test_create__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        spotify_library_factory: SpotifyLibraryFactory,
    ) -> None:
        spotify_library = spotify_library_factory.create(user, auth_token)
        assert isinstance(spotify_library, SpotifyLibraryAdapter)
        assert spotify_library.user == user
        assert spotify_library.session_client.auth_token == auth_token


class TestSpotifyLibrary:
    async def test__no_active_device(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_oauth: SpotifyOAuthAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{spotify_oauth.base_url}/me/player/play",
            method="PUT",
            status_code=codes.NOT_FOUND,
        )
        with pytest.raises(ProviderNoActiveDeviceException):
            await spotify_library.play_track("6rqhFgbbKwnb9MLmUQDhG6")

    async def test__premium_required(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_oauth: SpotifyOAuthAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{spotify_oauth.base_url}/me/player/play",
            method="PUT",
            status_code=codes.FORBIDDEN,
        )
        with pytest.raises(ProviderPremiumRequiredException):
            await spotify_library.play_track("6rqhFgbbKwnb9MLmUQDhG6")

    async def test__unhandled_http_error__reraises(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_oauth: SpotifyOAuthAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{spotify_oauth.base_url}/me/player/play",
            method="PUT",
            status_code=408,  # 4xx ≠ 429 → not retried by tenacity
        )
        with pytest.raises(httpx.HTTPStatusError):
            await spotify_library.play_track("6rqhFgbbKwnb9MLmUQDhG6")
