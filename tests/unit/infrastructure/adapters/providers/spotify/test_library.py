from unittest import mock

import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory


class TestSpotifyLibraryFactory:
    @pytest.fixture
    def spotify_library_factory(
        self,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_client: mock.AsyncMock,
    ) -> SpotifyLibraryFactory:
        return SpotifyLibraryFactory(
            auth_token_repository=mock_auth_token_repository,
            client=mock_provider_client,
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
