from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.infrastructure.entrypoints.cli.commands.playlist.discover import playlist_discover_logic

from tests.unit.factories.entities.playlist import PlaylistFactory


@pytest.mark.wiremock("openrouter")
@pytest.mark.usefixtures("openrouter_settings_wiremock")
class TestPlaylistDiscoverLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and avoid duplication.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.playlist.discover.DiscoverTasteUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    async def test__discover__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        discovery_artist_strategy: DiscoveryArtistStrategy,
        mock_use_case: mock.Mock,
    ) -> None:
        expected_result = DiscoverTasteResult(
            playlist=PlaylistFactory.build(user_id=user.id),
            strategy=discovery_artist_strategy,
            reports=[],
            tracks=[],
        )
        mock_use_case.create_suggestions_playlist.return_value = expected_result

        result = await playlist_discover_logic(
            email=user.email,
            provider=MusicProvider.SPOTIFY,
            config=DiscoverTasteConfigInput(),
            # The default advisor model is missing from the WireMock catalog: the check passes only with the override
            model="google/gemini-3.5-flash",
        )

        assert result == expected_result
